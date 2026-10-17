"""The doctrines under their own hostname (copied from the Shipyard's front door, runbook 14).

With DOCTRINES_HOST set (for example "doctrines.orlovfamily.space"):
- on that host every path outside the doctrines (and the SSO, static and account paths) leads to
  the landing page; a visitor who is not logged in is sent to auth's EVE SSO login and comes back
  through the bounce view /doctrines/go/; a member without the permission gets a short "not for
  you" page;
- on auth's own host every doctrines path redirects to the hostname, so the doctrines live at
  one address.
Without the setting nothing changes.
"""

from django.conf import settings
from django.shortcuts import redirect, render

from . import app_settings

PASS_PREFIXES = ("/doctrines/", "/sso/", "/static/", "/account/", "/media/", "/favicon")
BOUNCE_PATH = "/doctrines/go/"
PERMISSION = "doctrines.basic_access"


class DoctrinesHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = app_settings.host()
        request.doctrines_standalone = False
        if not host:
            return self.get_response(request)
        path = request.path
        request_host = request.get_host().split(":")[0].lower()
        if request_host == host:
            request.doctrines_standalone = True
            if not path.startswith(PASS_PREFIXES):
                return redirect("/doctrines/")
            if path.startswith("/doctrines/") and path != BOUNCE_PATH:
                user = getattr(request, "user", None)
                if user is None or not user.is_authenticated:
                    return redirect(f"{settings.SITE_URL.rstrip('/')}/sso/login?next={BOUNCE_PATH}")
                if not user.has_perm(PERMISSION):
                    return render(request, "doctrines/no_access.html", {"frame": "doctrines/frame_standalone.html", "standalone": True}, status=403)
        elif path.startswith("/doctrines/") and path != BOUNCE_PATH:
            return redirect(f"https://{host}{request.get_full_path()}")
        return self.get_response(request)
