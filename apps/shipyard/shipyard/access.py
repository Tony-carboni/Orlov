"""Who may enter the Shipyard, and which pages.

`basic_access` opens every page. The limited permissions (owner, 2026-10-12, first for Hamu)
open a few named pages each: `reprocessing_access` the Reprocessing tab, `dashboard_access`
the ship dashboard with its ship pages and My settings (the character picker). A member
with limited access is sent from any other Shipyard page to their first tab, and the
navigation shows only what they may open.
"""

from functools import wraps

from django.core.exceptions import PermissionDenied

FULL = "shipyard.basic_access"
LIMITED = {
    "shipyard.dashboard_access": {"index", "ship_detail", "api_simulate", "settings", "use_character", "set_facility", "set_bpc_price", "go"},
    "shipyard.reprocessing_access": {"reprocessing", "reprocessing_skills", "bargains", "use_character", "go"},
    "shipyard.books_access": {"finance", "finance_pdf", "finance_refresh", "hangar_refresh", "lplog", "go"},
}
# the tab a limited member lands on, in order of preference
LANDING = [("shipyard.dashboard_access", "/shipyard/"), ("shipyard.reprocessing_access", "/shipyard/reprocessing/"), ("shipyard.books_access", "/shipyard/finance/")]
ALL_TABS = ("index", "fuel", "reprocessing", "scrapmetal", "lp", "bargains", "industry", "business", "settings")


def has_full_access(user) -> bool:
    return bool(user and user.is_authenticated and user.has_perm(FULL))


def allowed_url_names(user):
    """None for full access (everything), else the set of url names the member may open."""
    if has_full_access(user):
        return None
    names = set()
    for perm, urls in LIMITED.items():
        if user.has_perm(perm):
            names |= urls
    return names


def may_enter(user) -> bool:
    """Any Shipyard page at all: full access or one of the limited permissions."""
    return bool(user and user.is_authenticated and (has_full_access(user) or any(user.has_perm(p) for p in LIMITED)))


def landing(user) -> str:
    for perm, path in LANDING:
        if user.has_perm(perm):
            return path
    return "/shipyard/"


def tabs(user) -> set:
    """Navigation entries this member sees."""
    if has_full_access(user):
        return set(ALL_TABS)
    names = allowed_url_names(user) or set()
    return {t for t in ALL_TABS if t in names}


def allows(url_name: str):
    """View decorator: full access, or a limited permission that covers this url name."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            names = allowed_url_names(request.user)
            if not request.user.is_authenticated or (names is not None and url_name not in names):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


# kept for callers of 0.9.7
reprocessing_allowed = allows("reprocessing")
