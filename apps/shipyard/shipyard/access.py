"""Who may enter the Shipyard.

`basic_access` opens every page. `reprocessing_access` (owner, 2026-10-12, first for Hamu)
opens the Reprocessing tab alone: the front door lets such a member in, lands them on that
tab, and the navigation shows nothing else.
"""

from functools import wraps

from django.core.exceptions import PermissionDenied

FULL = "shipyard.basic_access"
REPROCESSING = "shipyard.reprocessing_access"
REPROCESSING_PATH = "/shipyard/reprocessing/"


def has_full_access(user) -> bool:
    return bool(user and user.is_authenticated and user.has_perm(FULL))


def may_enter(user) -> bool:
    """Any Shipyard page at all: full access or the reprocessing-only permission."""
    return bool(user and user.is_authenticated and (user.has_perm(FULL) or user.has_perm(REPROCESSING)))


def reprocessing_allowed(view):
    """View decorator: full access or the reprocessing-only permission."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not may_enter(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped
