"""LP conversion: every offer of a militia's loyalty point store, valued at Jita.

ESI's public route /loyalty/stores/{corporation_id}/offers/ lists what the store sells: the item,
how many, the LP and ISK it costs and the items you must hand in. The tab (owner's request,
2026-10-19) values each offer at Jita's lowest sell, takes off the ISK and the inputs at Jita
sell, and shows the net ISK per LP, with Jita's daily volume and the depth of the sell orders.
A blueprint copy has no market price, so its row shows the price a copy must fetch to reach the
target rate (SHIPYARD_LP_TARGET_ISK_PER_LP, 900 by default): dearer copies on contracts are
the good offers.

Refreshes: offers daily (they rarely change), Jita prices hourly with the other tabs, volumes
daily (ESI history, one call per item).
"""

import logging
from dataclasses import dataclass, field

from django.utils import timezone

from .. import app_settings, constants
from ..models import LpOffer, LpTypeMarket, MarketLocation, MaterialType
from . import esi, fuzzwork
from .http import get_json, polite_pause
from .industry import ensure_type_names

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"


def store_corp_id() -> int:
    return int(app_settings.SHIPYARD_LP_STORE_CORP_ID)


def target() -> float:
    return float(app_settings.SHIPYARD_LP_TARGET_ISK_PER_LP)


def _station_id() -> int:
    m = MarketLocation.objects.filter(is_active=True).order_by("-is_default", "name").first()
    return int(m.station_id) if m else 60003760


def _type_ids(offers) -> set:
    ids = set()
    for o in offers:
        ids.add(int(o.type_id))
        ids.update(int(t) for t, _ in (o.required_items or []))
    return ids


# --- refresh -----------------------------------------------------------------------------

def refresh_offers() -> dict:
    """The store's offers from ESI into LpOffer; names into LpTypeMarket. Offers that are gone turn inactive."""
    cid = store_corp_id()
    data = get_json(f"{ESI}/loyalty/stores/{cid}/offers/", params={"datasource": "tranquility"})
    now = timezone.now()
    seen = set()
    for o in data or []:
        oid = int(o["offer_id"])
        seen.add(oid)
        LpOffer.objects.update_or_create(
            store_corp_id=cid, offer_id=oid,
            defaults={
                "type_id": int(o["type_id"]), "quantity": int(o.get("quantity") or 1),
                "lp_cost": int(o.get("lp_cost") or 0), "isk_cost": float(o.get("isk_cost") or 0),
                "ak_cost": int(o.get("ak_cost") or 0),
                "required_items": [[int(r["type_id"]), int(r.get("quantity") or 1)] for r in (o.get("required_items") or [])],
                "fetched_at": now, "is_active": True,
            },
        )
    gone = LpOffer.objects.filter(store_corp_id=cid, is_active=True).exclude(offer_id__in=seen).update(is_active=False)
    offers = list(LpOffer.objects.filter(store_corp_id=cid, is_active=True))
    ids = _type_ids(offers)
    ensure_type_names(ids)
    names = dict(MaterialType.objects.filter(type_id__in=ids).values_list("type_id", "name"))
    for tid in ids:
        name = names.get(tid, "")
        LpTypeMarket.objects.update_or_create(
            type_id=tid, defaults={"name": name or f"Type {tid}", "is_blueprint": name.endswith(" Blueprint")},
        )
    return {"offers": len(seen), "gone": gone, "types": len(ids)}


def refresh_prices() -> dict:
    """Jita lowest sell, order depth and highest buy for every type the store touches (Fuzzwork)."""
    ids = list(LpTypeMarket.objects.values_list("type_id", flat=True))
    if not ids:
        return {"types": 0}
    agg = fuzzwork.station_aggregates(_station_id(), ids)
    now = timezone.now()
    n = 0
    for tid, a in agg.items():
        LpTypeMarket.objects.filter(type_id=tid).update(
            sell_min=a["sell_min"], sell_volume=a["sell_volume"] or 0.0, sell_orders=a["sell_orders"], buy_max=a["buy_max"], prices_at=now,
        )
        n += 1
    return {"types": n}


def refresh_volumes() -> dict:
    """Daily volume at Jita's region for every item the store sells (not the blueprints, not the inputs)."""
    region = app_settings.SHIPYARD_HISTORY_REGION_ID
    days = app_settings.SHIPYARD_VOLUME_DAYS
    outputs = set(LpOffer.objects.filter(store_corp_id=store_corp_id(), is_active=True).values_list("type_id", flat=True))
    n, errors = 0, []
    for t in LpTypeMarket.objects.filter(type_id__in=outputs, is_blueprint=False):
        try:
            s = esi.volume_stats(region, t.type_id, days)
            LpTypeMarket.objects.filter(type_id=t.type_id).update(avg_daily_volume=s["avg_daily_volume"], volume_at=timezone.now())
            n += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{t.name}: {exc}")
            logger.warning("history failed for %s: %s", t, exc)
        polite_pause()
    return {"types": n, "errors": errors}


# --- the table ---------------------------------------------------------------------------

@dataclass
class LpRow:
    offer_id: int
    type_id: int
    name: str
    is_blueprint: bool
    quantity: int
    lp: int
    isk_cost: float
    inputs: list = field(default_factory=list)   # [(type_id, name, qty, unit sell, cost)]
    inputs_cost: float = 0.0
    inputs_complete: bool = True
    sell: float | None = None                     # Jita lowest sell per unit of the output
    buy: float | None = None
    output_value: float | None = None             # sell × quantity
    net: float | None = None                      # output after sales tax − ISK cost − inputs (owner, 2026-10-20)
    gross: float | None = None                    # output − ISK cost − inputs, before any tax
    isk_per_lp: float | None = None               # net per LP, after sales tax on the output
    isk_per_lp_gross: float | None = None         # before sales tax
    isk_per_lp_after: float | None = None         # after sales tax and broker fee on the sale
    avg_daily_volume: float = 0.0
    sell_volume: float = 0.0
    sell_orders: int = 0
    bpc_target: float | None = None               # what a blueprint copy must fetch for the target rate
    bpc_target_after: float | None = None         # the same when fees come off the sale

    @property
    def depth_days(self):
        return self.sell_volume / self.avg_daily_volume if self.avg_daily_volume else None

    @property
    def kind(self) -> str:
        return "blueprint" if self.is_blueprint else "item"


def rows(fees: float = 0.0, target_rate: float | None = None, sales_tax: float = 0.0) -> list[LpRow]:
    """One row per active offer. `sales_tax` (a fraction) comes off the output in Net and ISK/LP (owner,
    2026-10-20: profit always after the sales tax on what the store gives); `fees` = sales tax + broker fee,
    taken off the sale for the 'after fees' figures; `target_rate` for the blueprint price (the setting when
    not given). Blueprint copies sell on contracts, which charge no sales tax."""
    rate = target() if target_rate is None else float(target_rate)
    offers = list(LpOffer.objects.filter(store_corp_id=store_corp_id(), is_active=True))
    market = {m.type_id: m for m in LpTypeMarket.objects.filter(type_id__in=_type_ids(offers))}
    out = []
    for o in offers:
        m = market.get(o.type_id)
        row = LpRow(offer_id=o.offer_id, type_id=o.type_id, name=m.name if m else f"Type {o.type_id}", is_blueprint=bool(m and m.is_blueprint),
                    quantity=o.quantity, lp=o.lp_cost, isk_cost=float(o.isk_cost))
        for tid, qty in o.required_items or []:
            im = market.get(tid)
            unit = im.sell_min if im and im.sell_min else None
            cost = unit * qty if unit is not None else None
            row.inputs.append((tid, im.name if im else f"Type {tid}", qty, unit, cost))
            if cost is None:
                row.inputs_complete = False
            else:
                row.inputs_cost += cost
        costs = row.isk_cost + row.inputs_cost
        if m:
            row.avg_daily_volume = m.avg_daily_volume or 0.0
            row.sell_volume = m.sell_volume or 0.0
            row.sell_orders = m.sell_orders or 0
            row.buy = m.buy_max
        if row.is_blueprint:
            row.bpc_target = (rate * row.lp + costs) / row.quantity
            row.bpc_target_after = row.bpc_target / (1.0 - fees) if fees < 1 else None
        elif m and m.sell_min:
            row.sell = m.sell_min
            row.output_value = m.sell_min * row.quantity
            row.gross = row.output_value - costs
            row.net = row.output_value * (1.0 - sales_tax) - costs
            if row.lp > 0:
                row.isk_per_lp = row.net / row.lp
                row.isk_per_lp_gross = row.gross / row.lp
                row.isk_per_lp_after = (row.output_value * (1.0 - fees) - costs) / row.lp
        out.append(row)
    out.sort(key=lambda r: (-(r.isk_per_lp if r.isk_per_lp is not None else -1e18), r.name))
    return out


def freshness() -> dict:
    cid = store_corp_id()
    return {
        "offers": LpOffer.objects.filter(store_corp_id=cid).order_by("-fetched_at").values_list("fetched_at", flat=True).first(),
        "prices": LpTypeMarket.objects.exclude(prices_at=None).order_by("-prices_at").values_list("prices_at", flat=True).first(),
        "volumes": LpTypeMarket.objects.exclude(volume_at=None).order_by("-volume_at").values_list("volume_at", flat=True).first(),
    }
