"""The second front door: the Shipyard under its own hostname.

With SHIPYARD_STANDALONE_HOST set (for example "shipyards.orlovfamily.space"):
- on that host every path outside the Shipyard (and the SSO, static and account paths)
  leads to the dashboard, a visitor who is not logged in is sent to auth's EVE SSO login
  and comes back through the bounce view `/shipyard/go/`, and a member without the
  Shipyard permission gets a short "not for you" page;
- on auth's own host every Shipyard path redirects to the standalone host, so the
  Shipyard lives at one address.
Without the setting nothing changes. docs/research/06-shipyards-frontend.md
"""

from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve

from . import access, app_settings

PASS_PREFIXES = ("/shipyard/", "/sso/", "/static/", "/account/", "/media/", "/favicon")
BOUNCE_PATH = "/shipyard/go/"


class StandaloneHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = app_settings.standalone_host()
        request.shipyard_standalone = False
        if not host:
            return self.get_response(request)
        path = request.path
        request_host = request.get_host().split(":")[0].lower()
        if request_host == host:
            request.shipyard_standalone = True
            if not path.startswith(PASS_PREFIXES):
                return redirect("/shipyard/")
            if path.startswith("/shipyard/") and path != BOUNCE_PATH:
                user = getattr(request, "user", None)
                if user is None or not user.is_authenticated:
                    login = f"{settings.SITE_URL.rstrip('/')}/sso/login?next={BOUNCE_PATH}"
                    return redirect(login)
                if not access.may_enter(user):
                    return render(
                        request,
                        "shipyard/no_access.html",
                        {"frame": "shipyard/frame_standalone.html", "standalone": True},
                        status=403,
                    )
                names = access.allowed_url_names(user)
                if names is not None:
                    # limited members: every page outside their permission is their first tab
                    try:
                        match = resolve(path)
                        allowed = match.url_name in names
                    except Resolver404:
                        allowed = False
                    if not allowed:
                        return redirect(access.landing(user))
        elif path.startswith("/shipyard/") and path != BOUNCE_PATH:
            return redirect(f"https://{host}{request.get_full_path()}")
        return self.get_response(request)
