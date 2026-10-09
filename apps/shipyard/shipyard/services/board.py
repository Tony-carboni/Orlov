"""Assemble dashboard rows and ship details from stored snapshots (DB access here)."""

import logging
from dataclasses import dataclass

from django.core.cache import cache
from django.utils import timezone

from .. import app_settings, constants
from ..models import (
    BuildSnapshot, ContractPrice, Facility, MarketLocation, MaterialType, MemberBlueprintPrice, PriceSnapshot, Ship, ShipConfig,
    ShipMarketStats, UserSettings,
)
from . import contracts, everef, pricing

logger = logging.getLogger(__name__)


def get_user_settings(user) -> UserSettings:
    settings, _ = UserSettings.objects.get_or_create(user=user)
    changed = False
    if settings.facility is None or not settings.facility.is_active:
        settings.facility = Facility.objects.filter(is_active=True).order_by("-is_default", "name").first()
        changed = True
    if settings.market is None or not settings.market.is_active:
        settings.market = MarketLocation.objects.filter(is_active=True).order_by("-is_default", "name").first()
        changed = True
    if changed:
        settings.save()
    return settings


def _price_map(location, type_ids) -> dict:
    """{type_id: PriceSnapshot}"""
    if location is None:
        return {}
    return {p.type_id: p for p in PriceSnapshot.objects.filter(location=location, type_id__in=type_ids)}


def _name_volume_maps(type_ids):
    names, volumes = {}, {}
    for m in MaterialType.objects.filter(type_id__in=type_ids):
        names[m.type_id] = m.name
        volumes[m.type_id] = m.volume
    return names, volumes


@dataclass
class BoardRow:
    ship: Ship
    econ: pricing.ShipEconomics
    config: ShipConfig | None
    stats: ShipMarketStats | None
    build: BuildSnapshot | None
    owned_bp: dict | None = None  # the member's best blueprint for this ship, when it has one
    own_price: float | None = None  # the member's own typed blueprint price, when there is one
    contract: object = None  # ContractPrice row (Jita 4-4 contracts), information only


def dashboard_rows(settings: UserSettings, *, categories=None, exclude=None) -> list[BoardRow]:
    """Rows for the dashboard; `categories` keeps only those, `exclude` drops those (the fuel tab vs the ships)."""
    facility, market = settings.facility, settings.market
    rates = pricing.tax_rates(market, settings)
    qs = Ship.objects.filter(is_active=True)
    if categories:
        qs = qs.filter(category__in=list(categories))
    if exclude:
        qs = qs.exclude(category__in=list(exclude))
    ships = list(qs.order_by("name"))
    configs = {c.ship_id: c for c in ShipConfig.objects.select_related("lp_faction").filter(ship__in=ships)}
    stats = {s.ship_id: s for s in ShipMarketStats.objects.filter(ship__in=ships)}
    builds = {}
    if facility:
        default_me = {s.type_id: s.default_me_te[0] for s in ships}
        for b in BuildSnapshot.objects.filter(facility=facility, ship__in=ships):
            if b.me == default_me.get(b.ship_id):
                builds[b.ship_id] = b
    material_ids = set()
    for b in builds.values():
        material_ids.update(int(m["type_id"]) for m in b.materials)
    tag_ids = {c.tag_type_id for c in configs.values() if c.tag_type_id}
    type_ids = material_ids | {s.type_id for s in ships} | tag_ids
    # the member's own blueprints: their ME/TE replace the ME 0 snapshot for those ships
    from . import industry

    owned = industry.owned_blueprints(settings.user) if settings.user_id else {}
    own_prices = {}
    if settings.user_id:
        own_prices = {p.ship_id: float(p.price_isk) for p in MemberBlueprintPrice.objects.filter(user_id=settings.user_id)}
    contract_prices = contracts.fresh_prices()
    live_budget = industry.MAX_LIVE_BUILDS
    # materials of the live builds may not be in the snapshot's name map yet
    for ship in ships:
        bp = owned.get(ship.blueprint_type_id)
        if bp and facility and (bp["me"] or bp["te"]):
            material_ids.update(int(m["type_id"]) for m in builds[ship.type_id].materials) if ship.type_id in builds else None
    prices = _price_map(market, type_ids)
    names, volumes = _name_volume_maps(material_ids)
    unit_prices = {tid: (p.sell_min if p else None) for tid, p in prices.items()}

    rows = []
    for ship in ships:
        build = builds.get(ship.type_id)
        st = stats.get(ship.type_id)
        hull_price = prices.get(ship.type_id)
        cfg = configs.get(ship.type_id)
        bp = owned.get(ship.blueprint_type_id)
        material_rows = build.materials if build else []
        job_cost = build.job_cost if build else 0
        time_seconds = build.time_seconds if build else 0
        if bp and facility and (bp["me"], bp["te"]) != ship.default_me_te and live_budget > 0:
            try:
                data = simulate_build(ship, facility, me=bp["me"], te=bp["te"], settings=settings)
                material_rows, job_cost, time_seconds = data["materials"], data["job_cost"], data["time_seconds"]
                live_budget -= 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("live build with the member's blueprint failed for %s: %s", ship, exc)
        econ = pricing.economics(
            sell_price=hull_price.sell_min * ship.units_per_run if hull_price and hull_price.sell_min is not None else None,
            material_rows=material_rows,
            prices=unit_prices,
            names=names,
            volumes=volumes,
            job_cost=job_cost,
            config=configs.get(ship.type_id),
            use_lp=True,  # LP offers are the corp's price list; the policy per type decides the rest
            rates=rates,
            avg_daily_volume=st.avg_daily_volume if st else 0,
            sell_volume_on_market=hull_price.sell_volume if hull_price else 0,
            time_seconds=time_seconds,
            tag_unit_price=unit_prices.get(cfg.tag_type_id) if cfg and cfg.tag_type_id else None,
            category=ship.category,
            hull_size=ship.hull_size,
            markup=settings.markup_fraction,
            name=ship.name,
            own_price=own_prices.get(ship.type_id),
        )
        rows.append(BoardRow(ship=ship, econ=econ, config=cfg, stats=st, build=build, owned_bp=bp,
                             own_price=own_prices.get(ship.type_id), contract=contract_prices.get(ship.type_id)))
    rows.sort(key=lambda r: (r.econ.net_profit is None, -(r.econ.net_profit or 0)))
    return rows


def ship_detail(ship: Ship, settings: UserSettings, *, facility=None, me=None, te=None, bpc=None, tag=None, use_lp=None):
    """Economics for one ship; `me`, `bpc`, `tag`, `facility`, `use_lp` are ad-hoc overrides.

    ME 0 at a known facility comes from the stored snapshot; anything else is a live
    EVE Ref call (cached) so the dashboard numbers are never touched by simulations.
    """
    facility = facility or settings.facility
    market = settings.market
    rates = pricing.tax_rates(market, settings)
    config = ShipConfig.objects.select_related("lp_faction").filter(ship=ship).first()
    stats = ShipMarketStats.objects.filter(ship=ship).first()
    default_me, default_te = ship.default_me_te
    me = default_me if me is None else me
    te = default_te if te is None else te

    build = None
    if facility and (me, te) == (default_me, default_te):
        build = BuildSnapshot.objects.filter(ship=ship, facility=facility, me=me).first()
    if build:
        material_rows, job_cost, time_seconds = build.materials, build.job_cost, build.time_seconds
        source = "snapshot"
    elif facility:
        data = simulate_build(ship, facility, me=me, te=te, settings=settings)
        material_rows, job_cost, time_seconds = data["materials"], data["job_cost"], data["time_seconds"]
        source = "live"
    else:
        material_rows, job_cost, time_seconds, source = [], 0, 0, "none"

    material_ids = {int(m["type_id"]) for m in material_rows}
    tag_ids = {config.tag_type_id} if config and config.tag_type_id else set()
    prices = _price_map(market, material_ids | {ship.type_id} | tag_ids)
    names, volumes = _name_volume_maps(material_ids)
    unit_prices = {tid: (p.sell_min if p else None) for tid, p in prices.items()}
    hull_price = prices.get(ship.type_id)

    # ad-hoc overrides for the simulation panel
    sim_config = config
    if bpc is not None or tag is not None:
        # a typed tag amount replaces the market-priced tag and the extras together
        sim_config = ShipConfig(ship=ship,
                                bpc_price_isk=bpc if bpc is not None else (config.bpc_price_isk if config else 0),
                                tag_cost_isk=tag if tag is not None else (config.tag_cost_isk if config else 0),
                                tag_type_id=None if tag is not None else (config.tag_type_id if config else None),
                                tag_quantity=config.tag_quantity if config else 1,
                                lp_faction=config.lp_faction if config else None,
                                lp_cost=config.lp_cost if config else 0,
                                lp_isk_cost=config.lp_isk_cost if config else 0,
                                lp_runs=config.lp_runs if config else 1)
    if bpc is not None:
        use_lp = False  # a typed blueprint price always wins in the simulation
    if use_lp is None:
        use_lp = True
    # the member's own price from the dashboard, unless the simulation types another one
    own_price = None
    if bpc is None and settings.user_id:
        own = MemberBlueprintPrice.objects.filter(user_id=settings.user_id, ship=ship).first()
        own_price = float(own.price_isk) if own else None
    contract = contracts.fresh_prices([ship.type_id]).get(ship.type_id)  # shown for information only

    econ = pricing.economics(
        sell_price=hull_price.sell_min * ship.units_per_run if hull_price and hull_price.sell_min is not None else None,
        material_rows=material_rows,
        prices=unit_prices,
        names=names,
        volumes=volumes,
        job_cost=job_cost,
        config=sim_config,
        use_lp=use_lp,
        rates=rates,
        avg_daily_volume=stats.avg_daily_volume if stats else 0,
        sell_volume_on_market=hull_price.sell_volume if hull_price else 0,
        time_seconds=time_seconds,
        tag_unit_price=unit_prices.get(sim_config.tag_type_id) if sim_config and sim_config.tag_type_id else None,
        # a typed blueprint price is a real quote, so it overrides the policy for the simulation
        category=None if bpc is not None else ship.category,
        hull_size=ship.hull_size,
        markup=settings.markup_fraction,
        name=ship.name,
        own_price=own_price,
    )
    return {"econ": econ, "config": config, "stats": stats, "facility": facility, "market": market,
            "rates": rates, "source": source, "hull_price": hull_price, "me": me, "te": te,
            "contract": contract}


def simulate_build(ship: Ship, facility: Facility, *, me=0, te=0, settings=None) -> dict:
    """Live EVE Ref call for an ad-hoc ME/TE/facility combination, cached."""
    skills = {}
    if settings is not None:
        for field, param in constants.EVEREF_SKILL_PARAMS.items():
            skills[param] = getattr(settings, field, 5)
    key = f"shipyard:sim:{ship.type_id}:{facility.pk}:{me}:{te}:" + ":".join(f"{k}={v}" for k, v in sorted(skills.items()))
    data = cache.get(key)
    if data is None:
        block = everef.manufacturing_cost(
            ship.type_id,
            system_id=facility.system_id,
            structure_type_id=facility.structure_type_id or None,
            rig_type_ids=facility.rig_type_ids,
            facility_tax_pct=float(facility.facility_tax),
            me=me, te=te, skills=skills,
        )
        data = everef.normalise_cost_block(block)
        cache.set(key, data, app_settings.SHIPYARD_SIM_CACHE_SECONDS)
    return data


def data_freshness() -> dict:
    """Timestamps for the footer."""
    price = PriceSnapshot.objects.order_by("-fetched_at").values_list("fetched_at", flat=True).first()
    build = BuildSnapshot.objects.order_by("-fetched_at").values_list("fetched_at", flat=True).first()
    stats = ShipMarketStats.objects.order_by("-fetched_at").values_list("fetched_at", flat=True).first()
    contract = ContractPrice.objects.order_by("-snapshot_at").values_list("snapshot_at", flat=True).first()
    return {"prices": price, "builds": build, "stats": stats, "contracts": contract, "now": timezone.now()}
