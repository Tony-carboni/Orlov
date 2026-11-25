"""The Projects page (0.41.0): running projects with their flags, the completed ones, the ore prices, the permission gate."""
import datetime as dt

from allianceauth.tests.auth_utils import AuthUtils
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
                                   progress_current=10, progress_desired=1_000, reward_per_contribution=9_000, reward_remaining=8.9e6, created=NOW)
        CorpProject.objects.create(project_id="p-done", corporation_id=CORP, name="White Glaze", state="Completed", details=_deliver(28444),
                                   progress_current=500, progress_desired=500, reward_per_contribution=150_000, finished=NOW - dt.timedelta(days=2), created=NOW)
        CorpProject.objects.create(project_id="p-old", corporation_id=CORP, name="Old one", state="Completed", details=_deliver(28444),
                                   progress_current=5, progress_desired=5, finished=NOW - dt.timedelta(days=90), created=NOW - dt.timedelta(days=100))
        CorpProject.objects.create(project_id="p-gone", corporation_id=CORP, name="Gone", state="Active", missing=True, progress_current=1, progress_desired=2)
        CorpProject.objects.create(project_id="p-other", corporation_id=1, name="Other corp", state="Active", progress_current=1, progress_desired=2)

    def test_running_projects_fullest_first_with_their_flags(self):
        board = projectsboard.project_rows(done_days=30)
        self.assertEqual([(r["project"].name, r["flag"], r["item"], r["left"]) for r in board["running"]],
                         [("Veldspar", "nearly", "Compressed Veldspar", 20_000), ("Bitumens", "", "Compressed Bitumens", 990)])
        self.assertEqual([(r["project"].name, r["flag"]) for r in board["done"]], [("White Glaze", "done")])  # the 90-day-old one is out
        self.assertEqual(board["counts"], {"running": 2, "nearly": 1, "done": 1})

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

    def test_a_full_active_project_counts_as_done(self):
        p = CorpProject.objects.get(project_id="p-nearly")
        p.progress_current = p.progress_desired
        p.save()
        self.assertEqual(projectsboard.flag_of(p), "done")
        self.assertEqual([r["project"].name for r in projectsboard.project_rows()["done"]], ["Veldspar", "White Glaze"])

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
        self.assertIn("Compressed White Glaze", html)
        self.assertIn("90 % of Jita buy", html)
        self.assertIn('href="/shipyard/projects/board/"', html)  # the nav shows the tab
        from .. import access
        self.assertEqual(access.allowed_url_names(officer), {"projects_board", "use_character", "go"})  # not the full Corp projects page
        self.assertEqual(access.landing(officer), "/shipyard/projects/board/")
