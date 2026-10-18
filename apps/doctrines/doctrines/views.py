"""Three pages: the landing page (philosophy and the tiles per category), one doctrine (its ships
with fittings, cost, insurance and SRP), and the fitting as plain text. Plus the SSO bounce."""

import logging

from allianceauth.authentication.models import CharacterOwnership
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from esi.views import sso_redirect

from . import app_settings
from .models import Category, Doctrine, DoctrineShip, RefreshRun, SiteText, SrpRequest
from .services import fittings, prices, skills

logger = logging.getLogger(__name__)

PERMISSION = "doctrines.basic_access"
SSO_PENDING_KEY = "doctrines_sso_pending"  # session: the character the member is granting the skills scope for
SSO_NEXT_KEY = "doctrines_sso_next"  # session: the doctrine slug to return to


def _back(slug):
    """The page to return to after the character switch: that doctrine, else the landing page."""
    if slug and Doctrine.objects.filter(slug=slug).exists():
        return reverse("doctrines:doctrine", args=[slug])
    return reverse("doctrines:index")


def _context(request, **extra):
    standalone = getattr(request, "doctrines_standalone", False)
    context = {
        "frame": "doctrines/frame_standalone.html" if standalone else "doctrines/frame_auth.html",
        "standalone": standalone,
        "brand": app_settings.DOCTRINES_BRAND,
        "can_manage": request.user.has_perm("doctrines.manage_doctrines"),
        "can_srp": request.user.has_perm("doctrines.srp_agent"),
    }
    context.update(extra)
    return context


@login_required
@permission_required(PERMISSION)
def index(request):
    text = SiteText.objects.first()
    categories = []
    for c in Category.objects.all():
        doctrines = list(c.doctrines.filter(is_active=True).prefetch_related("ships"))
        if doctrines:
            categories.append({"category": c, "doctrines": doctrines})
    return render(request, "doctrines/index.html", _context(request, text=text, categories=categories))


@login_required
@permission_required(PERMISSION)
def doctrine(request, slug):
    d = get_object_or_404(Doctrine.objects.select_related("category"), slug=slug, is_active=True)
    ships = d.ships.filter(is_active=True).select_related("srp_level").order_by("order", "id")
    rows = fittings.page_data(ships, d.srp_percent)
    member = skills.ensure_fresh(skills.current(request.user))
    for r in rows:
        ship = r["ship"]
        if member is not None and ship.fitting_json:
            try:
                r["skills"] = skills.check(fittings.type_ids_of(ship), member.skills, fittings.type_names_of(ship))
            except Exception as exc:  # noqa: BLE001
                logger.warning("skills check of %s failed: %s", ship, exc)
                r["skills"] = None
        else:
            r["skills"] = None
    groups = fittings.grouped(rows)
    roles = fittings.by_role(groups)
    last_prices = RefreshRun.objects.filter(step="prices", ok=True).order_by("-started_at").first()
    return render(request, "doctrines/doctrine.html", _context(
        request, doctrine=d, rows=rows, groups=groups, roles=roles, market=fittings.market_name(),
        prices_at=prices.freshness(), prices_stale=prices.is_stale(), last_prices=last_prices,
        insurance_level=app_settings.DOCTRINES_INSURANCE_LEVEL,
        others=Doctrine.objects.filter(is_active=True).exclude(pk=d.pk).select_related("category"),
        member=member, characters=skills.choices(request.user, member),
    ))


@login_required
@permission_required(PERMISSION)
def use_character(request, character_id):
    """Run the skills check with one of the member's own characters.

    POST from the switch starts it. A character without a token that carries the skills scope
    is sent through EVE's login once; the member comes back here (GET) and the token is used.
    """
    ownership = get_object_or_404(CharacterOwnership.objects.select_related("character"), user=request.user, character__character_id=character_id)
    eve_character = ownership.character
    pending = request.session.pop(SSO_PENDING_KEY, None)
    back = request.POST.get("next") or request.session.pop(SSO_NEXT_KEY, None) or ""
    token = skills.token_for(request.user, character_id)
    if token is None and pending == character_id:
        messages.error(request, f"EVE's login did not give the skills scope for {eve_character.character_name}. Log in with that character and accept the scope, then try again.")
        return redirect(_back(back))
    if token is None:
        if request.method != "POST":
            return redirect(_back(back))
        request.session[SSO_PENDING_KEY] = character_id
        request.session[SSO_NEXT_KEY] = back
        return sso_redirect(request, scopes=skills.SCOPES)
    try:
        skills.load(request.user, token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("skills of %s not read: %s", eve_character.character_name, exc)
        messages.error(request, f"EVE did not answer when reading the skills of {eve_character.character_name}. Try again in a minute.")
        return redirect(_back(back))
    messages.success(request, f"Skills check now uses {eve_character.character_name}.")
    return redirect(_back(back))


@login_required
@permission_required(PERMISSION)
@require_POST
def character_refresh(request):
    """Read the current character's skills from EVE again."""
    member = skills.current(request.user)
    back = request.POST.get("next") or ""
    if member is None:
        return redirect(_back(back))
    token = skills.token_for(request.user, member.character_id)
    if token is None:
        messages.error(request, f"No token with the skills scope for {member.character_name} any more; choose the character again.")
        return redirect(_back(back))
    try:
        skills.load(request.user, token)
        messages.success(request, f"Skills of {member.character_name} read from EVE.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("skills refresh of %s failed: %s", member.character_name, exc)
        messages.error(request, "EVE did not answer. Try again in a minute.")
    return redirect(_back(back))


@login_required
@permission_required(PERMISSION)
def fit_text(request, pk):
    """The fitting as plain text, for members whose browser blocks the clipboard."""
    ship = get_object_or_404(DoctrineShip, pk=pk, is_active=True, doctrine__is_active=True)
    text = (ship.fitting_json or {}).get("text") or ship.fitting_text
    response = HttpResponse(text, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'inline; filename="{ship.ship_type_name or "fit"}.txt"'
    return response


@login_required
def go(request):
    """Bounce after auth's SSO login: back to the doctrines' own address."""
    host = app_settings.host()
    return redirect(f"https://{host}/doctrines/" if host else "/doctrines/")


# --- SRP -----------------------------------------------------------------------------------------

SRP_PERMISSION = "doctrines.srp_agent"


@login_required
@permission_required(SRP_PERMISSION)
def srp(request):
    from .services import srp as srp_service

    tab = request.GET.get("tab") or "open"
    counts = {row["status"]: row["n"] for row in SrpRequest.objects.values("status").annotate(n=Count("id"))}
    tabs = [(SrpRequest.OPEN, "Open", counts.get(SrpRequest.OPEN, 0)), (SrpRequest.REVIEW, "To review", counts.get(SrpRequest.REVIEW, 0)),
            (SrpRequest.PAID, "Paid", counts.get(SrpRequest.PAID, 0)), (SrpRequest.REJECTED, "Rejected", counts.get(SrpRequest.REJECTED, 0)), ("all", "All", sum(counts.values()))]
    qs = SrpRequest.objects.select_related("doctrine", "doctrine_ship")
    if tab != "all":
        qs = qs.filter(status=tab)
    return render(request, "doctrines/srp.html", _context(
        request, requests=qs[:300], tab=tab, tabs=tabs, market=fittings.market_name(),
        division=app_settings.DOCTRINES_SRP_WALLET_DIVISION, wallet_ok=srp_service.wallet_token() is not None,
    ))


@login_required
@permission_required(SRP_PERMISSION)
@require_POST
def srp_add(request):
    from .services import srp as srp_service

    kill_id = srp_service.kill_id_from(request.POST.get("kill", ""))
    if not kill_id:
        messages.error(request, "Give a zKillboard link or a kill id.")
        return redirect("doctrines:srp")
    try:
        record, created = srp_service.create_from_kill(kill_id, requested_by=request.user.username, source="manual")
    except Exception as exc:  # noqa: BLE001
        logger.warning("SRP add of %s by %s failed: %s", kill_id, request.user, exc)
        messages.error(request, f"The kill could not be read: {exc}")
        return redirect("doctrines:srp")
    if created:
        messages.success(request, f"Request #{record.pk} recorded: {record.pilot_name}, {record.ship_type_name}, {record.get_status_display().lower()}.")
    else:
        messages.info(request, f"Kill {kill_id} was requested before: #{record.pk}, {record.get_status_display().lower()}.")
    return redirect(f"{reverse('doctrines:srp')}?tab={record.status}")


@login_required
@permission_required(SRP_PERMISSION)
@require_POST
def srp_action(request, pk):
    record = get_object_or_404(SrpRequest, pk=pk)
    action = request.POST.get("action")
    who = request.user.username
    if action == "approve":
        raw = (request.POST.get("payout") or "").replace(",", "").replace(" ", "")
        try:
            payout = float(raw) if raw else record.payout
        except ValueError:
            payout = None
        if not payout:
            messages.error(request, "Give the payout in ISK before approving.")
            return redirect(f"{reverse('doctrines:srp')}?tab={record.status}")
        record.payout = payout
        record.status = SrpRequest.OPEN
        record.reviewed_by = who
        record.save()
        messages.success(request, f"#{record.pk} approved at {payout:,.0f} ISK.")
    elif action == "paid":
        record.mark_paid(note="marked by hand", by=who)
        messages.success(request, f"#{record.pk} marked paid.")
    elif action == "reject":
        record.status = SrpRequest.REJECTED
        record.reviewed_by = who
        record.save()
        messages.info(request, f"#{record.pk} rejected.")
    elif action == "reopen":
        record.status = SrpRequest.REVIEW if record.adhoc and not record.payout else SrpRequest.OPEN
        record.paid_at = None
        record.paid_amount = None
        record.paid_journal_id = None
        record.paid_note = ""
        record.reviewed_by = who
        record.save()
        messages.info(request, f"#{record.pk} reopened.")
    return redirect(f"{reverse('doctrines:srp')}?tab={record.status}")


@login_required
@permission_required(SRP_PERMISSION)
@require_POST
def srp_sync(request):
    from .services import srp as srp_service

    try:
        result = srp_service.match_payments()
    except Exception as exc:  # noqa: BLE001
        logger.warning("SRP wallet check by %s failed: %s", request.user, exc)
        messages.error(request, f"The wallet could not be read: {exc}")
        return redirect("doctrines:srp")
    (messages.success if result.get("ok") else messages.warning)(request, result.get("message", ""))
    return redirect("doctrines:srp")
