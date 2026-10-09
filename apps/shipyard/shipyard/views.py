import logging
from decimal import Decimal, InvalidOperation

from allianceauth.authentication.models import CharacterOwnership
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from esi.models import Token
from esi.views import sso_redirect

from . import app_settings, constants
from .models import (
    Facility, LpFaction, MarketLocation, MaterialType, MemberBlueprintPrice, PriceSnapshot, Ship, ShipConfig,
)
from .services import board, characters, industry, reprocessing, scrapmetal
from .services.pricing import tax_rates

logger = logging.getLogger(__name__)

SSO_PENDING_KEY = "shipyard_sso_pending"  # session: character the member is granting access for


def _context(request, **extra):
    """Every page: which frame to render in (auth's layout or the standalone front door)."""
    standalone = getattr(request, "shipyard_standalone", False)
    context = {
        "frame": "shipyard/frame_standalone.html" if standalone else "shipyard/frame_auth.html",
        "standalone": standalone,
    }
    context.update(extra)
    return context


def _dec(value, default=None):
    if value in (None, ""):
        return default
    try:
        return Decimal(str(value).replace(",", "").replace(" ", ""))
    except InvalidOperation:
        return default


def _int(value, default=0, lo=None, hi=None):
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


@login_required
@permission_required("shipyard.basic_access")
def index(request):
    settings = board.get_user_settings(request.user)
    data_notice = characters.ensure_fresh(settings, request.user)
    rows = board.dashboard_rows(settings, exclude=[constants.CAT_FUEL])
    context = _context(
        request,
        rows=rows,
        settings=settings,
        data_notice=data_notice,
        rates=tax_rates(settings.market, settings),
        facilities=Facility.objects.filter(is_active=True),
        markets=MarketLocation.objects.filter(is_active=True),
        categories=constants.CATEGORY_ORDER,
        hulls=constants.HULL_ORDER,
        freshness=board.data_freshness(),
        complete_rows=sum(1 for r in rows if r.econ.complete),
        can_manage=request.user.has_perm("shipyard.manage_shipyard"),
    )
    return render(request, "shipyard/index.html", context)


@login_required
@permission_required("shipyard.basic_access")
def fuel_view(request):
    """Fuel blocks tab: the ship dashboard for the four fuel blocks, figures per run of 40 blocks."""
    settings = board.get_user_settings(request.user)
    data_notice = characters.ensure_fresh(settings, request.user)
    rows = board.dashboard_rows(settings, categories=[constants.CAT_FUEL])
    context = _context(
        request,
        fuel=True,
        rows=rows,
        settings=settings,
        data_notice=data_notice,
        rates=tax_rates(settings.market, settings),
        facilities=Facility.objects.filter(is_active=True),
        markets=MarketLocation.objects.filter(is_active=True),
        categories=[],
        hulls=[],
        freshness=board.data_freshness(),
        complete_rows=sum(1 for r in rows if r.econ.complete),
        can_manage=request.user.has_perm("shipyard.manage_shipyard"),
        units_per_run=constants.FUEL_UNITS_PER_RUN,
    )
    return render(request, "shipyard/index.html", context)


@login_required
@permission_required("shipyard.basic_access")
def ship_detail(request, type_id):
    ship = get_object_or_404(Ship, type_id=type_id)
    settings = board.get_user_settings(request.user)
    data_notice = characters.ensure_fresh(settings, request.user)
    # the member's own blueprint for this ship sets the starting ME/TE
    owned = industry.owned_blueprints(request.user).get(ship.blueprint_type_id)
    if owned and (owned["me"] or owned["te"]):
        try:
            detail = board.ship_detail(ship, settings, me=owned["me"], te=owned["te"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("detail with the member's blueprint failed for %s: %s", ship, exc)
            detail = board.ship_detail(ship, settings)
    else:
        detail = board.ship_detail(ship, settings)
    context = _context(
        request,
        ship=ship,
        settings=settings,
        data_notice=data_notice,
        owned=owned,
        detail=detail,
        econ=detail["econ"],
        facilities=Facility.objects.filter(is_active=True),
        freshness=board.data_freshness(),
        can_manage=request.user.has_perm("shipyard.manage_shipyard"),
    )
    return render(request, "shipyard/ship_detail.html", context)


@login_required
@permission_required("shipyard.basic_access")
def api_simulate(request, type_id):
    """Ad-hoc simulation for the detail page. Never writes anything."""
    ship = get_object_or_404(Ship, type_id=type_id)
    settings = board.get_user_settings(request.user)
    me = _int(request.GET.get("me"), ship.default_me_te[0], 0, 10)
    te = _int(request.GET.get("te"), ship.default_me_te[1], 0, 20)
    facility = None
    if request.GET.get("facility"):
        facility = Facility.objects.filter(pk=_int(request.GET.get("facility")), is_active=True).first()
    bpc = _dec(request.GET.get("bpc"))
    tag = _dec(request.GET.get("tag"))
    use_lp = request.GET.get("use_lp")
    use_lp = (use_lp == "1") if use_lp in ("0", "1") else None
    try:
        d = board.ship_detail(ship, settings, facility=facility, me=me, te=te, bpc=bpc, tag=tag, use_lp=use_lp)
    except Exception as exc:  # noqa: BLE001
        logger.warning("simulation failed for %s: %s", ship, exc)
        return JsonResponse({"ok": False, "error": "Simulation service unavailable, try again in a minute."}, status=502)
    e = d["econ"]
    return JsonResponse({
        "ok": True,
        "source": d["source"],
        "me": me, "te": te,
        "facility": d["facility"].name if d["facility"] else None,
        "sell_price": e.sell_price,
        "material_cost": e.material_cost,
        "material_volume": e.material_volume,
        "job_cost": e.job_cost,
        "bpc_cost": e.bpc_cost,
        "bpc_source": e.bpc_source,
        "bpc_excluded": e.bpc_excluded,
        "bpc_markup": e.bpc_markup,
        "tag_cost": e.tag_cost,
        "sales_tax": e.sales_tax,
        "broker_fee": e.broker_fee,
        "total_cost": e.total_cost,
        "net_profit": e.net_profit,
        "margin": e.margin,
        "time_seconds": e.time_seconds,
        "missing_prices": e.missing_prices,
        "materials": [
            {"type_id": m.type_id, "name": m.name, "quantity": m.quantity, "unit_price": m.unit_price,
             "cost": m.cost, "volume": m.total_volume}
            for m in e.materials
        ],
    })


@login_required
@permission_required("shipyard.basic_access")
def settings_view(request):
    settings = board.get_user_settings(request.user)
    if request.method == "POST":
        fac = Facility.objects.filter(pk=_int(request.POST.get("facility")), is_active=True).first()
        market = MarketLocation.objects.filter(pk=_int(request.POST.get("market")), is_active=True).first()
        if fac:
            settings.facility = fac
        if market:
            settings.market = market
        if "use_lp_pricing" in request.POST:
            settings.use_lp_pricing = request.POST.get("use_lp_pricing") == "on"
        if "bpc_markup" in request.POST and request.user.has_perm("shipyard.manage_shipyard"):
            settings.bpc_markup = _dec(request.POST.get("bpc_markup"))
        # skills, standings and taxes come from ESI only; nothing is typed by hand any more
        settings.manual_sales_tax = None
        settings.manual_broker_fee = None
        settings.save()
        messages.success(request, "Shipyard settings saved.")
        return redirect(request.POST.get("next") or "shipyard:index")
    context = _context(
        request,
        settings=settings,
        facilities=Facility.objects.filter(is_active=True),
        markets=MarketLocation.objects.filter(is_active=True),
        characters=characters.choices(request.user, settings),
        scope_count=len(characters.full_scopes()),
        rates=tax_rates(settings.market, settings),
        standings=_market_standings(settings),
        next=request.GET.get("next", ""),
        default_markup=app_settings.SHIPYARD_CORP_BPC_MARKUP * 100,
    )
    return render(request, "shipyard/settings.html", context)


def _market_standings(settings):
    """What the broker fee uses at the chosen market, for the settings page."""
    market = settings.market
    if market is None or not market.is_npc_station or not (market.owner_faction_id or market.owner_corporation_id):
        return {"applies": False}
    return {
        "applies": True,
        "known": bool(settings.standings),
        "faction": settings.standing_with(market.owner_faction_id),
        "corp": settings.standing_with(market.owner_corporation_id),
    }


@login_required
@permission_required("shipyard.basic_access")
@require_POST
def set_facility(request, pk):
    """The Swap button on the dashboard: build at this facility from now on."""
    facility = get_object_or_404(Facility, pk=pk, is_active=True)
    settings = board.get_user_settings(request.user)
    settings.facility = facility
    settings.save(update_fields=["facility"])
    messages.success(request, f"Building at {facility.name}.")
    return redirect("shipyard:index")


@login_required
@permission_required("shipyard.basic_access")
@require_POST
def set_bpc_price(request, type_id):
    """Right-click on the dashboard's Blueprint cell: the member's own price for this copy.

    A blank or zero price removes the member's entry, the corp's policy applies again.
    """
    ship = get_object_or_404(Ship, type_id=type_id, is_active=True)
    price = _dec(request.POST.get("price"))
    if price is None or price <= 0:
        deleted, _ = MemberBlueprintPrice.objects.filter(user=request.user, ship=ship).delete()
        if deleted:
            messages.info(request, f"{ship.name}: your blueprint price is cleared, the corp's figure applies again.")
    else:
        MemberBlueprintPrice.objects.update_or_create(user=request.user, ship=ship, defaults={"price_isk": price})
        messages.success(request, f"{ship.name}: blueprint priced at {price:,.0f} ISK per run in your numbers.")
    if request.POST.get("next") == "detail":
        return redirect("shipyard:ship_detail", type_id=ship.type_id)
    return redirect("shipyard:index")


REFRESH_COOLDOWN_KEY = "shipyard:refresh_now"
REFRESH_COOLDOWN_SECONDS = 300


@login_required
@permission_required("shipyard.manage_shipyard")
@require_POST
def refresh_now(request):
    """Refresh button on the dashboard (managers): queue the hourly refreshes right away.

    Jita prices, sales volumes and the contract prices. Builds and indices are not
    included (they take minutes of EVE Ref calls and change rarely). One click per
    five minutes; the beat schedule keeps running regardless.
    """
    from . import tasks
    # back to the tab the button was pressed on
    back = request.POST.get("next", "index")
    target = "shipyard:" + (back if back in ("index", "reprocessing", "scrapmetal") else "index")
    if cache.get(REFRESH_COOLDOWN_KEY):
        messages.info(request, "A refresh was started less than five minutes ago; the numbers update as it finishes.")
        return redirect(target)
    cache.set(REFRESH_COOLDOWN_KEY, timezone.now().isoformat(), REFRESH_COOLDOWN_SECONDS)
    tasks.refresh_prices_and_stats.delay()
    tasks.refresh_contract_prices.delay()
    logger.info("manual refresh queued by %s", request.user)
    messages.success(request, "Refresh started: Jita prices, sales volumes and contract prices. Reload the page in about a minute.")
    return redirect(target)


@login_required
@permission_required("shipyard.basic_access")
def use_character(request, character_id):
    """Make one of the member's auth characters the dashboard's character.

    POST from the picker starts it; the member comes back here (GET) after EVE's login
    when the character had no token with the full scope set yet.
    """
    ownership = get_object_or_404(
        CharacterOwnership.objects.select_related("character"), user=request.user, character__character_id=character_id
    )
    eve_character = ownership.character
    token = characters.token_for(request.user, character_id)
    pending = request.session.pop(SSO_PENDING_KEY, None)
    if token is None and pending == character_id:
        # back from EVE's login without the token we asked for: maybe another of the
        # member's characters was used; then that one is just as good
        recent = (
            Token.objects.filter(user=request.user)
            .require_scopes(characters.full_scopes())
            .require_valid()
            .order_by("-created")
            .first()
        )
        if recent and CharacterOwnership.objects.filter(user=request.user, character__character_id=recent.character_id).exists():
            messages.info(request, f"EVE's login was done with {recent.character_name}, so that character is used.")
            return redirect("shipyard:use_character", character_id=recent.character_id)
        messages.error(
            request,
            f"EVE's login did not give full access for {eve_character.character_name}. "
            "Log in with that character and accept all scopes, then try again.",
        )
        return redirect("shipyard:settings")
    if token is None:
        if request.method != "POST":
            return redirect("shipyard:settings")
        request.session[SSO_PENDING_KEY] = character_id
        return sso_redirect(request, scopes=characters.full_scopes())
    settings = board.get_user_settings(request.user)
    try:
        characters.load_character(settings, token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("character load failed for %s: %s", eve_character.character_name, exc)
        messages.error(request, f"EVE did not answer when reading {eve_character.character_name}. Try again in a minute.")
        return redirect("shipyard:settings")
    added = characters.register_in_memberaudit(eve_character)
    note = " The character was also registered in Member Audit." if added else ""
    messages.success(request, f"Using {eve_character.character_name}: skills and standings loaded from EVE.{note}")
    return redirect("shipyard:index")


@login_required
@permission_required("shipyard.basic_access")
def reprocessing_view(request):
    """Reprocessing tab: compressed ore and ice worth buying at Jita to reprocess."""
    settings = board.get_user_settings(request.user)
    rows = reprocessing.dashboard_rows(settings.market)
    context = _context(
        request,
        rows=rows,
        settings=settings,
        setup=reprocessing.setup_summary(),
        kinds=[(k, reprocessing.KIND_LABELS[k]) for k in reprocessing.KINDS],
        families=reprocessing.families_by_kind(),
        variants=reprocessing.variants_present(),
        rarities=reprocessing.rarities_present(),
        areas=reprocessing.areas_present(),
        price_points=list(app_settings.SHIPYARD_REPRO_PRICE_POINTS),
        freshness=board.data_freshness(),
        complete_rows=sum(1 for r in rows if r.complete),
        can_manage=request.user.has_perm("shipyard.manage_shipyard"),
    )
    return render(request, "shipyard/reprocessing.html", context)


@login_required
@permission_required("shipyard.basic_access")
def scrapmetal_view(request):
    """Scrapmetal tab: modules worth buying at Jita to reprocess for their minerals."""
    settings = board.get_user_settings(request.user)
    rows = scrapmetal.dashboard_rows(settings.market, settings)
    context = _context(
        request,
        rows=rows,
        settings=settings,
        setup=scrapmetal.setup_summary(settings),
        groups=scrapmetal.groups_present(),
        variants=scrapmetal.variants_present(),
        price_points=list(app_settings.SHIPYARD_SCRAP_PRICE_POINTS),
        freshness=board.data_freshness(),
        complete_rows=sum(1 for r in rows if r.complete),
        can_manage=request.user.has_perm("shipyard.manage_shipyard"),
    )
    return render(request, "shipyard/scrapmetal.html", context)


@login_required
@permission_required("shipyard.basic_access")
def industry_view(request):
    """Jobs, blueprints and stock of the member's characters; POST = refresh now."""
    settings = board.get_user_settings(request.user)
    notices = industry.sync_user(request.user, force=request.method == "POST")
    if request.method == "POST":
        if not notices:
            messages.success(request, "Read from EVE again.")
        return redirect("shipyard:industry")
    # who may be looked at: own characters, the corp, the alliance (permissions on the director groups)
    scope = request.GET.get("scope", "own")
    if scope not in industry.allowed_scopes(request.user):
        scope = "own"
    data = industry.overview(request.user, scope=scope)
    return render(request, "shipyard/industry.html", _context(request, settings=settings, notices=notices, **data))


@login_required
def go(request):
    """Bounce after auth's SSO login: back to the Shipyard's own address."""
    host = app_settings.standalone_host()
    if host:
        return redirect(f"https://{host}/shipyard/")
    return redirect("shipyard:index")


@login_required
@permission_required("shipyard.manage_shipyard")
def blueprints(request):
    """Manager page: blueprint and tag prices per ship, LP prices per faction."""
    if request.method == "POST":
        with transaction.atomic():
            for lp in LpFaction.objects.all():
                v = _dec(request.POST.get(f"lp_{lp.pk}"))
                if v is not None and v != lp.isk_per_lp:
                    lp.isk_per_lp = v
                    lp.save(update_fields=["isk_per_lp"])
            factions = {str(f.pk): f for f in LpFaction.objects.all()}
            for cfg in ShipConfig.objects.select_related("ship").all():
                p = cfg.ship_id
                changed = False
                for field in ("bpc_price_isk", "tag_cost_isk", "lp_isk_cost"):
                    v = _dec(request.POST.get(f"{field}_{p}"))
                    if v is not None and v != getattr(cfg, field):
                        setattr(cfg, field, v)
                        changed = True
                for field in ("lp_cost", "lp_runs", "tag_quantity"):
                    raw = request.POST.get(f"{field}_{p}")
                    if raw not in (None, ""):
                        v = _int(raw, getattr(cfg, field), 0 if field == "lp_cost" else 1)
                        if v != getattr(cfg, field):
                            setattr(cfg, field, v)
                            changed = True
                raw_t = request.POST.get(f"tag_type_id_{p}")
                if raw_t is not None:
                    v = _int(raw_t, 0, 0) or None
                    if v != cfg.tag_type_id:
                        cfg.tag_type_id = v
                        changed = True
                raw_f = request.POST.get(f"lp_faction_{p}")
                if raw_f is not None:
                    f = factions.get(raw_f)
                    if (f.pk if f else None) != cfg.lp_faction_id:
                        cfg.lp_faction = f
                        changed = True
                if changed:
                    cfg.save()
        messages.success(request, "Blueprint and LP prices saved.")
        return redirect("shipyard:blueprints")
    configs = list(
        ShipConfig.objects.select_related("ship", "lp_faction")
        .filter(ship__is_active=True)
        .order_by("ship__category", "ship__hull_size", "ship__name")
    )
    # show what the market-priced tags currently cost at the default market
    tag_ids = {c.tag_type_id for c in configs if c.tag_type_id}
    market = MarketLocation.objects.filter(is_default=True, is_active=True).first()
    tag_prices = {}
    if market and tag_ids:
        tag_prices = {
            p.type_id: p.sell_min
            for p in PriceSnapshot.objects.filter(location=market, type_id__in=tag_ids)
        }
    tag_names = dict(MaterialType.objects.filter(type_id__in=tag_ids).values_list("type_id", "name"))
    for c in configs:
        c.tag_price = tag_prices.get(c.tag_type_id) if c.tag_type_id else None
        c.tag_name = tag_names.get(c.tag_type_id) if c.tag_type_id else None
    context = _context(
        request,
        settings=board.get_user_settings(request.user),
        configs=configs,
        lp_factions=LpFaction.objects.all(),
        market=market,
    )
    return render(request, "shipyard/blueprints.html", context)
