from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings

from ..middleware import StandaloneHostMiddleware
from ..models import UserSettings
from ..services import characters

HOST = "shipyards.example.org"


def _ok(request):
    return HttpResponse("ok")


@override_settings(SHIPYARD_STANDALONE_HOST=HOST, SITE_URL="https://auth.example.org", ALLOWED_HOSTS=["*"])
class StandaloneHostMiddlewareTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.mw = StandaloneHostMiddleware(_ok)
        self.user = get_user_model().objects.create_user("tony", password="x")
        self.member = get_user_model().objects.create_user("member", password="x")
        self.member.user_permissions.add(Permission.objects.get(codename="basic_access", content_type__app_label="shipyard"))

    def _request(self, path, host, user=None):
        request = self.rf.get(path, HTTP_HOST=host)
        request.user = user or AnonymousUser()
        return request

    def test_root_of_the_standalone_host_is_the_dashboard(self):
        response = self.mw(self._request("/", HOST))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/shipyard/")

    def test_visitor_is_sent_to_auth_sso_login_with_the_bounce_as_next(self):
        response = self.mw(self._request("/shipyard/", HOST))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://auth.example.org/sso/login?next=/shipyard/go/")

    def test_member_with_access_passes(self):
        request = self._request("/shipyard/", HOST, self.member)
        response = self.mw(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(request.shipyard_standalone)

    def test_user_without_access_gets_the_no_access_page(self):
        with mock.patch("shipyard.middleware.render", return_value=HttpResponse("no", status=403)) as render:
            response = self.mw(self._request("/shipyard/", HOST, self.user))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(render.call_args[0][1], "shipyard/no_access.html")

    def test_sso_and_static_paths_pass_untouched(self):
        for path in ("/sso/callback/?code=1", "/static/x.css", "/account/logout/"):
            self.assertEqual(self.mw(self._request(path, HOST)).status_code, 200, path)

    def test_bounce_path_is_left_alone_on_both_hosts(self):
        self.assertEqual(self.mw(self._request("/shipyard/go/", HOST, self.member)).status_code, 200)
        self.assertEqual(self.mw(self._request("/shipyard/go/", "auth.example.org", self.member)).status_code, 200)

    def test_shipyard_paths_on_the_auth_host_redirect_to_the_standalone_host(self):
        response = self.mw(self._request("/shipyard/ship/17740/?me=5", "auth.example.org", self.member))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"https://{HOST}/shipyard/ship/17740/?me=5")

    def test_other_paths_on_the_auth_host_are_untouched(self):
        request = self._request("/dashboard/", "auth.example.org", self.member)
        self.assertEqual(self.mw(request).status_code, 200)
        self.assertFalse(request.shipyard_standalone)

    @override_settings(SHIPYARD_STANDALONE_HOST="")
    def test_without_the_setting_nothing_changes(self):
        request = self._request("/shipyard/", "auth.example.org")
        self.assertEqual(self.mw(request).status_code, 200)
        self.assertFalse(request.shipyard_standalone)


class CharacterServiceTests(TestCase):
    def test_full_scopes_fall_back_to_our_copy(self):
        with mock.patch.dict("sys.modules", {"memberaudit": None, "memberaudit.models": None}):
            scopes = characters.full_scopes()
        self.assertIn("esi-characters.read_blueprints.v1", scopes)
        self.assertIn("esi-industry.read_character_jobs.v1", scopes)
        self.assertEqual(len(scopes), 33)

    def test_stale_without_character_or_timestamp(self):
        self.assertTrue(characters.is_stale(UserSettings()))
        self.assertTrue(characters.is_stale(UserSettings(skills_character_id=1)))

    def test_ensure_fresh_without_character_does_nothing(self):
        user = get_user_model().objects.create_user("tony", password="x")
        self.assertIsNone(characters.ensure_fresh(UserSettings(user=user), user))
