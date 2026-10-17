"""Three pages: the landing page (philosophy and the tiles per category), one doctrine (its ships
with fittings, cost, insurance and SRP), and the fitting as plain text. Plus the SSO bounce."""

import logging

from allianceauth.authentication.models import CharacterOwnership
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from esi.views import sso_redirect

from . import app_settings
from .models import Category, Doctrine, DoctrineShip, RefreshRun, SiteText
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
