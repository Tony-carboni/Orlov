"""Three pages: the landing page (philosophy and the tiles per category), one doctrine (its ships
with fittings, cost, insurance and SRP), and the fitting as plain text. Plus the SSO bounce."""

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import app_settings
from .models import Category, Doctrine, DoctrineShip, RefreshRun, SiteText
from .services import fittings, prices

PERMISSION = "doctrines.basic_access"


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
    rows = fittings.page_data(ships)
    groups = fittings.grouped(rows)
    last_prices = RefreshRun.objects.filter(step="prices", ok=True).order_by("-started_at").first()
    return render(request, "doctrines/doctrine.html", _context(
        request, doctrine=d, rows=rows, groups=groups, market=fittings.market_name(),
        prices_at=prices.freshness(), prices_stale=prices.is_stale(), last_prices=last_prices,
        insurance_level=app_settings.DOCTRINES_INSURANCE_LEVEL,
        others=Doctrine.objects.filter(is_active=True).exclude(pk=d.pk).select_related("category"),
    ))


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
