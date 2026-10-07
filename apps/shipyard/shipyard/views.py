import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from esi.decorators import token_required

from . import constants
from .models import Facility, LpFaction, MarketLocation, Ship, ShipConfig, UserSettings
from .services import board, esi
from .services.pricing import tax_rates

logger = logging.getLogger(__name__)

SKILL_SCOPES = ["esi-skills.read_skills.v1"]


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
    rows = board.dashboard_rows(settings)
    context = {
        "rows": rows,
        "settings": settings,
        "rates": tax_rates(settings.market, settings),
        "facilities": Facility.objects.filter(is_active=True),
        "markets": MarketLocation.objects.filter(is_active=True),
        "categories": constants.CATEGORY_ORDER,
        "hulls": constants.HULL_ORDER,
        "freshness": board.data_freshness(),
        "complete_rows": sum(1 for r in rows if r.econ.complete),
        "can_manage": request.user.has_perm("shipyard.manage_shipyard"),
    }
    return render(request, "shipyard/index.html", context)


@login_required
@permission_required("shipyard.basic_access")
def ship_detail(request, type_id):
    ship = get_object_or_404(Ship, type_id=type_id)
    settings = board.get_user_settings(request.user)
    detail = board.ship_detail(ship, settings)
    context = {
        "ship": ship,
        "settings": settings,
        "detail": detail,
        "econ": detail["econ"],
        "facilities": Facility.objects.filter(is_active=True),
        "freshness": board.data_freshness(),
        "can_manage": request.user.has_perm("shipyard.manage_shipyard"),
    }
    return render(request, "shipyard/ship_detail.html", context)


@login_required
@permission_required("shipyard.basic_access")
def api_simulate(request, type_id):
    """Ad-hoc simulation for the detail page. Never writes anything."""
    ship = get_object_or_404(Ship, type_id=type_id)
    settings = board.get_user_settings(request.user)
    me = _int(request.GET.get("me"), 0, 0, 10)
    te = _int(request.GET.get("te"), 0, 0, 20)
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
        settings.use_lp_pricing = request.POST.get("use_lp_pricing") == "on"
        if request.POST.get("skills_mode") == "manual":
            settings.skills_source = UserSettings.SKILLS_MANUAL
            for field, _, _ in constants.RELEVANT_SKILLS.values():
                setattr(settings, field, _int(request.POST.get(field), 0, 0, 5))
        settings.manual_sales_tax = _dec(request.POST.get("manual_sales_tax"))
        settings.manual_broker_fee = _dec(request.POST.get("manual_broker_fee"))
        settings.save()
        messages.success(request, "Shipyard settings saved.")
        return redirect(request.POST.get("next") or "shipyard:index")
    context = {
        "settings": settings,
        "facilities": Facility.objects.filter(is_active=True),
        "markets": MarketLocation.objects.filter(is_active=True),
        "skills": [
            (field, label, effect, getattr(settings, field))
            for _, (field, label, effect) in constants.RELEVANT_SKILLS.items()
        ],
        "rates": tax_rates(settings.market, settings),
        "next": request.GET.get("next", ""),
    }
    return render(request, "shipyard/settings.html", context)


@login_required
@permission_required("shipyard.basic_access")
@token_required(scopes=SKILL_SCOPES)
def load_skills(request, token):
    """Pull the relevant skills of the chosen character through ESI."""
    settings = board.get_user_settings(request.user)
    try:
        levels = esi.character_skills(token.character_id, token.valid_access_token())
    except Exception as exc:  # noqa: BLE001
        logger.warning("skill load failed for %s: %s", token.character_name, exc)
        messages.error(request, f"Could not read skills for {token.character_name} from ESI. Try again later.")
        return redirect("shipyard:settings")
    for skill_id, (field, _, _) in constants.RELEVANT_SKILLS.items():
        setattr(settings, field, levels.get(skill_id, 0))
    settings.skills_source = UserSettings.SKILLS_ESI
    settings.skills_character_id = token.character_id
    settings.skills_character_name = token.character_name
    settings.skills_fetched_at = timezone.now()
    settings.save()
    messages.success(request, f"Skills loaded from {token.character_name}.")
    return redirect("shipyard:settings")


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
                for field in ("lp_cost", "lp_runs"):
                    raw = request.POST.get(f"{field}_{p}")
                    if raw not in (None, ""):
                        v = _int(raw, getattr(cfg, field), 0 if field == "lp_cost" else 1)
                        if v != getattr(cfg, field):
                            setattr(cfg, field, v)
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
    configs = (
        ShipConfig.objects.select_related("ship", "lp_faction")
        .filter(ship__is_active=True)
        .order_by("ship__category", "ship__hull_size", "ship__name")
    )
    context = {
        "configs": configs,
        "lp_factions": LpFaction.objects.all(),
    }
    return render(request, "shipyard/blueprints.html", context)
