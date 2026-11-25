"""The Projects page (0.41.0): running projects with their flags, the completed ones, the ore prices, the permission gate."""
import datetime as dt
from unittest import mock

from allianceauth.tests.auth_utils import AuthUtils
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import CorpProject, MarketLocation, PriceSnapshot
from ..services import projectsboard

CORP = 98843356
NOW = dt.datetime(2026, 11, 25, 12, 0, tzinfo=dt.timezone.utc)


def _deliver(type_id):
    return {"configuration": [{"deliver_item": {"items": [{"type_id": type_id}]}}]}


@override_settings(SHIPYARD_STANDALONE_HOST="", SHIPYARD_PROJECTS_CORP_ID=CORP)
class ProjectsBoardTests(TestCase):
    def setUp(self):
        self.market = MarketLocation.objects.create(name="Jita", station_id=60003760, is_default=True)
        PriceSnapshot.objects.create(type_id=62516, location=self.market, buy_max=1_234.5, sell_min=1_300, fetched_at=NOW)
        PriceSnapshot.objects.create(type_id=62454, location=self.market, buy_max=9_876.0, sell_min=10_000, fetched_at=NOW)
        CorpProject.objects.create(project_id="p-nearly", corporation_id=CORP, name="Veldspar", state="Active", details=_deliver(62516),
                                   progress_current=80_000, progress_desired=100_000, reward_per_contribution=1_000, reward_remaining=20e6, created=NOW)
        CorpProject.objects.create(project_id="p-young", corporation_id=CORP, name="Bitumens", state="Active", details=_deliver(62454),
                                   progress_current=10, progress_desired=1_000, reward_per_contribution=10_200, reward_remaining=8.9e6, created=NOW)
        CorpProject.objects.create(project_id="p-done", corporation_id=CORP, name="White Glaze", state="Completed", details=_deliver(28444),
                                   progress_current=500, progress_desired=500, reward_per_contribution=150_000, finished=NOW - dt.timedelta(days=2), created=NOW)
        CorpProject.objects.create(project_id="p-old", corporation_id=CORP, name="Old one", state="Completed", details=_deliver(28444),
                                   progress_current=5, progress_desired=5, finished=NOW - dt.timedelta(days=90), created=NOW - dt.timedelta(days=100))
        CorpProject.objects.create(project_id="p-gone", corporation_id=CORP, name="Gone", state="Active", missing=True, progress_current=1, progress_desired=2)
        CorpProject.objects.create(project_id="p-other", corporation_id=1, name="Other corp", state="Active", progress_current=1, progress_desired=2)

    def test_running_projects_fullest_first_with_their_flags(self):
        board = projectsboard.project_rows()
        self.assertEqual([(r["project"].name, r["flag"], r["item"], r["left"]) for r in board["running"]],
                         [("Veldspar", "nearly", "Compressed Veldspar", 20_000), ("Bitumens", "", "Compressed Bitumens", 990)])
        self.assertEqual(board["counts"], {"running": 2, "nearly": 1, "full": 0, "price": 1})  # the projects EVE closed are not listed

    def test_the_price_check_flags_a_stale_reward(self):
        rows = {r["project"].name: r for r in projectsboard.project_rows()["running"]}
        self.assertEqual((round(rows["Veldspar"]["price_pct"], 1), rows["Veldspar"]["price_flag"]), (81.0, ""))  # 80 to 100 is fine
        self.assertEqual((round(rows["Bitumens"]["price_pct"], 1), rows["Bitumens"]["price_flag"]), (103.3, "high"))
        self.assertEqual(projectsboard.price_check(900, 1_000), (90.0, ""))
        self.assertEqual(projectsboard.price_check(800, 1_000), (80.0, ""))  # the band is inclusive
        self.assertEqual(projectsboard.price_check(799, 1_000), (79.9, "low"))
        self.assertEqual(projectsboard.price_check(1_000, 1_000), (100.0, ""))
        self.assertEqual(projectsboard.price_check(1_001, 1_000), (100.1, "high"))
        self.assertEqual(projectsboard.price_check(1_000, None), (None, ""))  # not priced: no check
        CorpProject.objects.create(project_id="p-ice", corporation_id=CORP, name="Ice", state="Active", details=_deliver(28444),
                                   progress_current=1, progress_desired=10, reward_per_contribution=150_000, created=NOW)
        PriceSnapshot.objects.create(type_id=28444, location=self.market, buy_max=100_000, fetched_at=NOW)
        ice = next(r for r in projectsboard.project_rows()["running"] if r["project"].name == "Ice")
        self.assertEqual((ice["price_pct"], ice["price_flag"]), (None, ""))  # the ice has its own rate
        sections = {s["family"]: s for s in projectsboard.project_rows()["sections"]}
        self.assertEqual((sections["Bitumens"]["price"], sections["Veldspar"]["price"], sections["Ice"]["price"]), (1, 0, 0))

    def test_sections_per_ore_family_with_the_missing_grades(self):
        sections = {s["family"]: s for s in projectsboard.project_rows()["sections"]}
        self.assertEqual([s["family"] for s in projectsboard.project_rows()["sections"]],
                         ["Veldspar", "Scordite", "Plagioclase", "Omber", "Kernite", "Pyroxeres", "Bitumens", "Coesite", "Sylvite", "Zeolites", "Ice"])
        self.assertEqual([r["project"].name for r in sections["Veldspar"]["rows"]], ["Veldspar"])
        self.assertEqual(sections["Veldspar"]["missing"], ["Compressed Veldspar II-Grade", "Compressed Veldspar III-Grade"])
        self.assertEqual((sections["Veldspar"]["nearly"], sections["Veldspar"]["kind_label"]), (1, "Asteroid ore"))
        self.assertEqual(sections["Bitumens"]["missing"], ["Compressed Brimful Bitumens", "Compressed Glistening Bitumens"])
        self.assertEqual((sections["Ice"]["rows"], sections["Ice"]["missing"]), ([], ["Compressed White Glaze"]))
        self.assertEqual(projectsboard.classify("Compressed Glistening Zeolites"), ("moon", "Zeolites", "Glistening"))
        self.assertEqual(projectsboard.classify("Compressed Omber III-Grade"), ("asteroid", "Omber", "III-Grade"))
        self.assertEqual(projectsboard.classify("Compressed White Glaze"), ("ice", "Ice", "White Glaze"))
        self.assertEqual(projectsboard.classify("Zero-Point Condensate"), ("other", "Other", ""))

    def test_a_full_active_project_stays_listed_as_full_until_eve_closes_it(self):
        p = CorpProject.objects.get(project_id="p-nearly")
        p.progress_current = p.progress_desired
        p.save()
        self.assertEqual(projectsboard.flag_of(p), "done")
        board = projectsboard.project_rows()
        self.assertEqual([(r["project"].name, r["flag"]) for r in board["running"]], [("Veldspar", "done"), ("Bitumens", "")])
        self.assertEqual((board["counts"]["full"], board["counts"]["nearly"]), (1, 0))
        self.assertEqual(next(s for s in board["sections"] if s["family"] == "Veldspar")["full"], 1)

    def test_ore_prices_are_90_pct_of_jita_buy_and_the_ice_is_fixed(self):
        prices = projectsboard.ore_prices()
        by_name = {r["name"]: r for g in prices["groups"] for r in g["rows"]}
        self.assertAlmostEqual(by_name["Compressed Veldspar"]["buy"], 1_111.05)  # 90 % of 1,234.5
        self.assertAlmostEqual(by_name["Compressed Bitumens"]["buy"], 8_888.4)
        self.assertIsNone(by_name["Compressed Omber"]["buy"])  # not priced yet
        self.assertEqual((by_name["Compressed White Glaze"]["buy"], by_name["Compressed White Glaze"]["fixed"]), (150_000.0, True))
        self.assertEqual([g["title"] for g in prices["groups"]], ["Highsec R4 moon ores", "Highsec asteroid ores", "Ice"])
        self.assertEqual([r["name"] for r in prices["groups"][2]["rows"]], ["Compressed White Glaze"])  # the one ice
        self.assertEqual((by_name["Compressed Brimful Bitumens"]["family"], by_name["Compressed Brimful Bitumens"]["grade"]), ("Bitumens", "Brimful"))
        self.assertEqual(prices["fetched_at"], NOW)
        self.assertNotIn(28444, projectsboard.price_type_ids())  # the ice is never priced from the market
        self.assertIn(62467, projectsboard.price_type_ids())
        self.assertIn(62536, projectsboard.price_type_ids())  # Kernite is priced too (owner, 2026-11-25)
        self.assertEqual([r["name"] for r in prices["groups"][1]["rows"]][-6:], ["Compressed Kernite", "Compressed Kernite II-Grade", "Compressed Kernite III-Grade", "Compressed Pyroxeres", "Compressed Pyroxeres II-Grade", "Compressed Pyroxeres III-Grade"])

    def test_the_page_needs_the_projects_permission(self):
        officer = get_user_model().objects.create_user("bern", password="x")
        AuthUtils.add_main_character_2(officer, "Bern Akiga", 3002, corp_id=CORP, corp_name="OARMI", alliance_id=None, alliance_name="")
        client = Client()
        client.force_login(officer)
        self.assertEqual(client.get(reverse("shipyard:projects_board")).status_code, 403)
        officer.user_permissions.add(Permission.objects.get(codename="projects_access", content_type__app_label="shipyard"))
        officer = get_user_model().objects.get(pk=officer.pk)  # permission cache
        client.force_login(officer)
        r = client.get(reverse("shipyard:projects_board"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Nearly full", html)
        self.assertNotIn("Completed projects", html)
        self.assertIn("Compressed White Glaze", html)
        self.assertIn("90 % of Jita buy", html)
        self.assertIn("Remake, pays too much", html)
        self.assertIn('href="/shipyard/projects/board/"', html)  # the nav shows the tab
        from .. import access
        self.assertEqual(access.allowed_url_names(officer), {"projects_board", "projects_board_refresh", "use_character", "go"})  # not the full Corp projects page
        self.assertEqual(access.landing(officer), "/shipyard/projects/board/")
        # the button reads the projects, at most once every two minutes
        cache.delete("shipyard:projects_board_refresh")
        with mock.patch("shipyard.services.projects.refresh", return_value={"projects": 25, "snapshots": 3, "contributions": 1}) as read:
            r = client.post(reverse("shipyard:projects_board_refresh"))
            self.assertEqual((r.status_code, r.url, read.call_count), (302, "/shipyard/projects/board/", 1))
            r = client.post(reverse("shipyard:projects_board_refresh"))
            self.assertEqual((r.status_code, read.call_count), (302, 1))  # the second press within two minutes does not read again
        cache.delete("shipyard:projects_board_refresh")
        self.assertEqual(client.get(reverse("shipyard:projects_board_refresh")).status_code, 405)  # POST only
