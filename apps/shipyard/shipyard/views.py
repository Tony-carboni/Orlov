import datetime as dt
import logging
from decimal import Decimal, InvalidOperation

from allianceauth.authentication.models import CharacterOwnership
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from esi.models import Token
from esi.views import sso_redirect

from . import access, app_settings, constants
from .models import (
    CorpProject, Facility, LpFaction, MarketLocation, MaterialType, MemberBlueprintPrice, PriceSnapshot, RefreshRun, Ship,
    ShipConfig, WalletDivision, WalletJournalEntry,
)
from .services import board, business, characters, industry, ledger, lpstore, projectbooks, projects, reprocessing, scrapmetal, wallet
from .services.pricing import tax_rates

logger = logging.getLogger(__name__)

SSO_PENDING_KEY = "shipyard_sso_pending"  # session: character the member is granting access for
SSO_NEXT_KEY = "shipyard_sso_next"  # session: the tab the picker was used from ("settings" or "reprocessing")


def _context(request, **extra):
    """Every page: which frame to render in (auth's layout or the standalone front door)."""
    standalone = getattr(request, "shipyard_standalone", False)
    context = {
        "frame": "shipyard/frame_standalone.html" if standalone else "shipyard/frame_auth.html",
        "standalone": standalone,
        "full_access": access.has_full_access(request.user),
        "tabs": access.tabs(request.user),
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
@access.allows("index")
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


def _books_allowed(user) -> bool:
    return user.has_perm("shipyard.manage_shipyard") or user.has_perm("shipyard.books_access")


@login_required
def finance(request):
    """Finance: the directors' balance sheet against the owner's working budget, live from our copies (0.17.0)."""
    from django.core.exceptions import PermissionDenied
    from .services import books
    if not _books_allowed(request.user):
        raise PermissionDenied
    try:
        data = books.compute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("balance sheet failed: %s", exc)
        data = None
        messages.error(request, f"The balance sheet could not be built: {exc}")
    return render(request, "shipyard/finance.html", _context(request, d=data, can_manage=request.user.has_perm("shipyard.manage_shipyard")))


@login_required
def finance_pdf(request):
    from django.core.exceptions import PermissionDenied
    from django.http import HttpResponse
    from .services import books, books_pdf
    if not _books_allowed(request.user):
        raise PermissionDenied
    data = books.compute()
    if data is None:
        messages.error(request, "No baseline yet: add one in the admin (Shipyard → books baseline).")
        return redirect("shipyard:finance")
    try:
        pdf = books_pdf.render(data)
    except ImportError:
        messages.error(request, "The PDF library (reportlab) is not installed on the server yet.")
        return redirect("shipyard:finance")
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="oarmi-balance-sheet-{data["cut"]:%Y-%m-%d-%H%M}.pdf"'
    return response


@login_required
@require_POST
def finance_refresh(request):
    from django.core.exceptions import PermissionDenied
    from .services import books
    if not _books_allowed(request.user):
        raise PermissionDenied
    messages.info(request, "Read from EVE: " + "; ".join(books.refresh()) + ". EVE itself refreshes the corporation's journal and transactions once an hour.")
    return redirect("shipyard:finance")


def _member_facility(request):
    """The facility the member preview shows: ?facility=<pk>, else the corp's default."""
    pk = _int(request.GET.get("facility"), 0)
    return Facility.objects.filter(pk=pk, is_active=True).first() if pk else None


@login_required
@permission_required("shipyard.manage_shipyard")
def member_view(request):
    """Member shipyards (owner, 2026-10-20): the ship dashboard exactly as a new member sees it, built
    from board.member_settings() instead of the owner's own settings, so his markup, character,
    own blueprints and own prices play no part. ?facility=<pk> previews another facility. Nothing is saved."""
    facility = _member_facility(request)
    settings = board.member_settings(facility)
    rows = board.dashboard_rows(settings, exclude=[constants.CAT_FUEL])
    context = _context(
        request,
        member_preview=True,
        member_query=f"?facility={facility.pk}" if facility else "",
        ship_url_name="shipyard:member_ship",
        rows=rows,
        settings=settings,
        rates=tax_rates(settings.market, settings),
        facilities=Facility.objects.filter(is_active=True),
        markets=MarketLocation.objects.filter(is_active=True),
        categories=constants.CATEGORY_ORDER,
        hulls=constants.HULL_ORDER,
        freshness=board.data_freshness(),
        complete_rows=sum(1 for r in rows if r.econ.complete),
        can_manage=False,
    )
    return render(request, "shipyard/index.html", context)


@login_required
@permission_required("shipyard.manage_shipyard")
def member_ship(request, type_id):
    """A ship page of the member preview: the member's settings, no own blueprint."""
    ship = get_object_or_404(Ship, type_id=type_id)
    facility = _member_facility(request)
    settings = board.member_settings(facility)
    detail = board.ship_detail(ship, settings)
    context = _context(
        request,
        member_preview=True,
        member_query=f"?facility={facility.pk}" if facility else "",
        ship=ship,
        settings=settings,
        owned=None,
        detail=detail,
        econ=detail["econ"],
        facilities=Facility.objects.filter(is_active=True),
        freshness=board.data_freshness(),
        can_manage=False,
    )
    return render(request, "shipyard/ship_detail.html", context)


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
@access.allows("ship_detail")
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
@access.allows("api_simulate")
def api_simulate(request, type_id):
    """Ad-hoc simulation for the detail page. Never writes anything."""
    ship = get_object_or_404(Ship, type_id=type_id)
    if request.GET.get("as") == "member" and request.user.has_perm("shipyard.manage_shipyard"):
        settings = board.member_settings()  # the member preview's ship page
    else:
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
@access.allows("settings")
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
        scope_count=len(characters.requested_scopes()),
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
@access.allows("set_facility")
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
@access.allows("set_bpc_price")
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
@access.allows("use_character")
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
    back = request.POST.get("next") or request.session.pop(SSO_NEXT_KEY, None) or "settings"
    back_url = "shipyard:reprocessing" if back == "reprocessing" else "shipyard:settings"
    if token is None and pending == character_id:
        request.session.pop(SSO_NEXT_KEY, None)
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
        return redirect(back_url)
    if token is None:
        if request.method != "POST":
            return redirect(back_url)
        request.session[SSO_PENDING_KEY] = character_id
        request.session[SSO_NEXT_KEY] = back
        return sso_redirect(request, scopes=characters.requested_scopes())
    settings = board.get_user_settings(request.user)
    try:
        characters.load_character(settings, token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("character load failed for %s: %s", eve_character.character_name, exc)
        messages.error(request, f"EVE did not answer when reading {eve_character.character_name}. Try again in a minute.")
        return redirect(back_url)
    added = characters.register_in_memberaudit(eve_character)
    note = " The character was also registered in Member Audit." if added else ""
    messages.success(request, f"Using {eve_character.character_name}: skills and standings loaded from EVE.{note}")
    if back == "reprocessing":
        return redirect("shipyard:reprocessing")
    return redirect("shipyard:index")


@login_required
@access.allows("reprocessing")
@require_POST
def reprocessing_skills(request):
    """The skills card on the Reprocessing tab: save typed levels, read them from EVE, or go back to V."""
    settings = board.get_user_settings(request.user)
    implant = _int(request.POST.get("implant"), 4, 0, 4)
    settings.repro_implant = 2 if implant == 3 else implant
    settings.save(update_fields=["repro_implant"])
    messages.success(request, "Implant saved; the table uses it now.")
    return redirect("shipyard:reprocessing")


@login_required
@access.allows("reprocessing")
def reprocessing_view(request):
    """Reprocessing tab: compressed ore and ice worth buying at Jita to reprocess."""
    settings = board.get_user_settings(request.user)
    # the tab only works with a chosen character: its skills are what the table is about
    token = characters.token_for(request.user, settings.skills_character_id) if settings.skills_character_id else None
    if token is None:
        return render(request, "shipyard/reprocessing_pick.html", _context(
            request, settings=settings, characters=characters.choices(request.user, settings),
            scope_count=len(characters.requested_scopes()), can_manage=request.user.has_perm("shipyard.manage_shipyard"),
        ))
    data_notice = characters.ensure_fresh(settings, request.user)
    settings = board.get_user_settings(request.user)
    rows = reprocessing.dashboard_rows(settings.market, settings)
    context = _context(
        request,
        rows=rows,
        settings=settings,
        setup=reprocessing.setup_summary(settings),
        data_notice=data_notice,
        kinds=[(k, reprocessing.KIND_LABELS[k]) for k in reprocessing.KINDS],
        families=reprocessing.families_by_kind(),
        variants=reprocessing.variants_present(),
        rarities=reprocessing.rarities_present(),
        areas=reprocessing.areas_present(),
        price_points=list(app_settings.SHIPYARD_REPRO_PRICE_POINTS),
        buyback_pct=f"{app_settings.SHIPYARD_BUYBACK_SHARE * 100:.0f} %",
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
    path = access.landing(request.user) if not access.has_full_access(request.user) else "/shipyard/"
    if host:
        return redirect(f"https://{host}{path}")
    return redirect(path)


WALLET_SSO_KEY = "shipyard_wallet_sso"  # session: we sent the member to EVE's login for the wallet scopes
PROJECTS_SSO_KEY = "shipyard_projects_sso"
BUSINESS_SSO_KEY = "shipyard_business_sso"


@login_required
@permission_required("shipyard.manage_shipyard")
def projects_view(request):
    """Corp projects: what runs, what was paid out per period, who contributed."""
    period = request.GET.get("period", "week")
    if period not in projects.PERIODS:
        period = "week"
    days = _int(request.GET.get("days"), 90, 0, 3650)
    since = timezone.now() - dt.timedelta(days=days) if days else None
    rows = list(CorpProject.objects.filter(corporation_id=projects.corp_id()).order_by("missing", "-created"))
    deltas = projects.payout_deltas(since)
    cdeltas = projects.contributor_deltas(since)
    active = [p for p in rows if p.state == "Active" and not p.missing]
    context = _context(
        request,
        settings=board.get_user_settings(request.user),
        period=period,
        periods=projects.PERIODS,
        days=days,
        token=projects.token(),
        corp_id=projects.corp_id(),
        projects=rows,
        active=active,
        pool_remaining=sum(p.reward_remaining for p in active),
        paid_all=sum(p.paid_out for p in rows),
        paid_range=sum(d["paid"] for d in deltas),
        pivot=projects.pivot(deltas, period),
        contributors=projects.contributors(cdeltas, period),
        books=projectbooks.books(),
        ledger_token=ledger.token(),
        ledger_run=RefreshRun.objects.filter(step="ledger").order_by("-started_at").first(),
        last_run=RefreshRun.objects.filter(step="projects").order_by("-started_at").first(),
        can_manage=True,
    )
    return render(request, "shipyard/projects.html", context)


@login_required
@access.allows("lp")
def lp_view(request):
    """LP conversion: every offer of the militia's LP store, valued at Jita, net ISK per LP."""
    settings = board.get_user_settings(request.user)
    rates = tax_rates(settings.market, settings)
    fees = rates.sales_tax + rates.broker_fee
    rows = lpstore.rows(fees=fees, sales_tax=rates.sales_tax)
    context = _context(
        request,
        settings=settings,
        rows=rows,
        sales_tax=rates.sales_tax,
        item_rows=sum(1 for r in rows if not r.is_blueprint),
        bpc_rows=sum(1 for r in rows if r.is_blueprint),
        fees=fees,
        target=lpstore.target(),
        store_name=app_settings.SHIPYARD_LP_STORE_NAME,
        volume_days=app_settings.SHIPYARD_VOLUME_DAYS,
        freshness=lpstore.freshness(),
        can_manage=request.user.has_perm("shipyard.manage_shipyard"),
    )
    return render(request, "shipyard/lp.html", context)


@login_required
@permission_required("shipyard.manage_shipyard")
@require_POST
def lp_refresh(request):
    from . import tasks
    tasks.refresh_lp_store.delay()
    messages.success(request, "LP store refresh started: offers, Jita prices and daily volumes. Reload the page in a minute or two.")
    return redirect("shipyard:lp")


@login_required
@permission_required("shipyard.manage_shipyard")
def projects_connect(request):
    if projects.token() is not None:
        messages.info(request, "A projects token exists already; the hourly refresh uses it.")
        return redirect("shipyard:projects")
    if request.session.pop(PROJECTS_SSO_KEY, None):
        messages.error(request, "EVE's login did not give the projects scope for a character of the corporation. Log in with a character of Orlov Arms International and accept the scope.")
        return redirect("shipyard:projects")
    request.session[PROJECTS_SSO_KEY] = True
    return sso_redirect(request, scopes=projects.scopes())


@login_required
@permission_required("shipyard.manage_shipyard")
@require_POST
def projects_refresh(request):
    try:
        result = projects.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning("projects refresh by %s failed: %s", request.user, exc)
        messages.error(request, f"The projects could not be read: {exc}")
        return redirect("shipyard:projects")
    messages.success(request, f"Projects read: {result['projects']} projects, {result['snapshots']} new snapshots, {result['contributions']} contribution rows.")
    return redirect("shipyard:projects")


@login_required
@permission_required("shipyard.manage_shipyard")
def wallet_view(request):
    """Structure income: the structure corp's wallet, as a ledger and as business intelligence."""
    period = request.GET.get("period", "week")
    if period not in wallet.PERIODS:
        period = "week"
    days = _int(request.GET.get("days"), 0, 0, 3650)
    since = timezone.now() - dt.timedelta(days=days) if days else None
    excluded = wallet.excluded_payers()
    all_income = list(wallet.income_entries(since))
    entries = wallet.without_excluded(all_income, excluded)  # the figures leave the excluded payers out
    all_entries = WalletJournalEntry.objects.filter(corporation_id=wallet.corp_id()).order_by("-date")[:2000]
    last_run = RefreshRun.objects.filter(step="wallet").order_by("-started_at").first()
    context = _context(
        request,
        settings=board.get_user_settings(request.user),
        period=period,
        periods=wallet.PERIODS,
        days=days,
        token=wallet.token(),
        corp_id=wallet.corp_id(),
        divisions=WalletDivision.objects.filter(corporation_id=wallet.corp_id()).order_by("division"),
        totals=wallet.totals(entries),
        pivot=wallet.pivot(entries, period),
        payers=[{**p, "excluded": p["id"] in excluded} for p in wallet.payers(all_income, period)],
        excluded=excluded,
        excluded_names=sorted(x.party_name or f"#{x.party_id}" for x in excluded.values()),
        entries=all_entries,
        ref_types=sorted({e.ref_type for e in all_entries}),
        income_types=list(app_settings.SHIPYARD_INCOME_REF_TYPES),
        last_run=last_run,
        can_manage=True,
    )
    return render(request, "shipyard/wallet.html", context)


@login_required
@permission_required("shipyard.manage_shipyard")
def wallet_connect(request):
    """Grant the wallet scopes once with a character of the structure corp (EVE's login)."""
    if wallet.token() is not None:
        messages.info(request, "A wallet token exists already; the hourly refresh uses it.")
        return redirect("shipyard:wallet")
    if request.session.pop(WALLET_SSO_KEY, None):
        # back from EVE's login without a usable token: wrong character or scopes declined
        messages.error(
            request,
            "EVE's login did not give the wallet scopes for a character of the structure corp. "
            "Log in with the structure corp's CEO or an accountant and accept both scopes.",
        )
        return redirect("shipyard:wallet")
    request.session[WALLET_SSO_KEY] = True
    return sso_redirect(request, scopes=wallet.scopes())


@login_required
@permission_required("shipyard.manage_shipyard")
@require_POST
def wallet_toggle_payer(request, party_id):
    """The checkbox in "Who pays": tick = counted in the income figures, untick = left out."""
    include = request.POST.get("include") == "1"
    name = (request.POST.get("name") or "")[:100]
    state = wallet.set_excluded(int(party_id), excluded=not include, by=request.user.username, name=name)
    messages.info(request, f"{name or party_id} is {'left out of' if state else 'counted in'} the income figures from now on.")
    back = request.POST.get("next") or ""
    return redirect(back if back.startswith("/") else reverse("shipyard:wallet"))


@login_required
@permission_required("shipyard.manage_shipyard")
@require_POST
def wallet_refresh(request):
    from . import tasks
    try:
        result = wallet.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning("wallet refresh by %s failed: %s", request.user, exc)
        messages.error(request, f"The wallet could not be read: {exc}")
        return redirect("shipyard:wallet")
    messages.success(request, f"Wallet read: {result['added']} new entries, {result['total']} in the ledger.")
    return redirect("shipyard:wallet")


@login_required
@access.allows("business")
def business_view(request):
    """My business: the member's chosen character's wallet and ship sales (Member Audit), the production corp's jobs."""
    period = request.GET.get("period", "week")
    if period not in business.PERIODS:
        period = "week"
    days = _int(request.GET.get("days"), 90, 0, 3650)
    since = timezone.now() - dt.timedelta(days=days) if days else None
    can_manage = request.user.has_perm("shipyard.manage_shipyard")
    # "me" = every character on this auth account (the owner's alts install the jobs; 0.22.2); managers may see the whole corp
    who = request.GET.get("who", "me") if can_manage else "me"
    if who not in ("me", "corp"):
        who = "me"
    my_ids = list(CharacterOwnership.objects.filter(user=request.user).values_list("character__character_id", flat=True))
    settings = board.get_user_settings(request.user)
    character_id = settings.skills_character_id
    ma = business.ma_character(character_id)
    journal = business.journal_rows(ma, since) if ma else []
    sales_rows = business.sales_rows(ma, since) if ma else []
    production_rows = business.production_rows(installer_ids=None if who == "corp" else my_ids, since=since)
    sales = business.sales_summary(sales_rows, period)
    production = business.production_summary(production_rows, period)
    wallet_summary = business.wallet_summary(journal, period)
    lp = business.lp_summary(production_rows, period, business.lp_balances(ma))
    ma_since = None
    if ma:
        try:
            from memberaudit.models import CharacterWalletTransaction
            first = CharacterWalletTransaction.objects.filter(character=ma).order_by("date").values_list("date", flat=True).first()
            ma_since = first
        except Exception:  # noqa: BLE001
            ma_since = None
    context = _context(
        request,
        settings=settings,
        character_id=character_id,
        character_name=settings.skills_character_name,
        ma_character=ma,
        ma_since=ma_since,
        freshness=business.ma_freshness(ma),
        balance=business.wallet_balance(ma) if ma else None,
        period=period, periods=business.PERIODS, days=days, who=who, installer_only=who != "corp", my_characters=len(my_ids),
        corp_id=business.corp_id(), token=business.token(),
        last_run=RefreshRun.objects.filter(step="corp_jobs").order_by("-started_at").first(),
        sales=sales, production=production, wallet=wallet_summary, lp=lp,
        comparison=business.compare(sales, production),
        fuel_table=business.fuel_table(sales, production),
        charts={
            "sold_category": business.chart(sales["by_category"]),
            "sold_hull": business.chart(sales["by_hull"]),
            "produced_category": business.chart(production["by_category"]),
            "wallet": business.wallet_chart(wallet_summary),
            "fuel_sold": business.chart(sales["fuel_by_name"]),
            "fuel_produced": business.chart(production["fuel_by_name"]),
            "isk_category": business.chart(sales["isk_by_category"]),
            "lp_faction": business.chart(lp["by_faction"]),
        },
        can_manage=can_manage,
    )
    return render(request, "shipyard/business.html", context)


@login_required
@permission_required("shipyard.manage_shipyard")
def business_connect(request):
    """Grant the corporation jobs scope once with a character of the production corp (EVE's login)."""
    if business.token() is not None:
        messages.info(request, "A jobs token exists already; the hourly refresh uses it.")
        return redirect("shipyard:business")
    if request.session.pop(BUSINESS_SSO_KEY, None):
        messages.error(request, "EVE's login did not give the corporation jobs scope for a character of the production corp. Log in with a character of Orlov Arms International that holds the Factory Manager role and accept the scope.")
        return redirect("shipyard:business")
    request.session[BUSINESS_SSO_KEY] = True
    return sso_redirect(request, scopes=business.scopes())


@login_required
@permission_required("shipyard.manage_shipyard")
@require_POST
def business_refresh(request):
    try:
        result = business.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning("corp jobs refresh by %s failed: %s", request.user, exc)
        messages.error(request, f"The jobs could not be read: {exc}")
        return redirect("shipyard:business")
    messages.success(request, f"Jobs read: {result['added']} new, {result['updated']} updated, {result['total']} kept.")
    return redirect("shipyard:business")


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
