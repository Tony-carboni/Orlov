"""The pages: permission gate, landing tiles per category, a doctrine page with cost, insurance and SRP, the fit text."""
from allianceauth.tests.auth_utils import AuthUtils
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import Category, Doctrine, DoctrineShip, Insurance, ItemType, SiteText, SrpLevel, TypePrice
from ..services import fittings

FIT = "[Harpy, Rail Harpy v3]\nDamage Control II\n150mm Railgun II, Spike S\nHobgoblin II x2\nSpike S x500\n"


@override_settings(DOCTRINES_HOST="")  # the pages on auth's host; the live settings may carry the real hostname
class PageTests(TestCase):
    def setUp(self):
        self.user = AuthUtils.create_user("reader")
        AuthUtils.add_main_character_2(self.user, "Reader Main", 1001, corp_id=2001, corp_name="Corp", corp_ticker="CORP")
        self.user = AuthUtils.add_permission_to_user_by_name("doctrines.basic_access", self.user)
        self.outsider = AuthUtils.create_user("outsider")
        AuthUtils.add_main_character_2(self.outsider, "Outsider Main", 1002, corp_id=2002, corp_name="Other", corp_ticker="OTHR")
        SiteText.objects.create(title="How we fly", body="Short of nothing.\n\n- bring what fits\n- fly together")
        light = Category.objects.create(name="Light & cheap", order=1)
        Category.objects.create(name="APEX", order=4)
        srp = SrpLevel.objects.create(name="Full", order=1, colour="success")
        self.doc = Doctrine.objects.create(category=light, name="Rail Harpies", gameplay="Home defense", summary="Fast kiting frigates")
        for tid, name, slot in ((11381, "Harpy", "ship"), (2048, "Damage Control II", "low"), (3074, "150mm Railgun II", "high"),
                                (12814, "Spike S", "charge"), (2456, "Hobgoblin II", "drone")):
            ItemType.objects.create(type_id=tid, name=name, slot=slot)
        ship = DoctrineShip(doctrine=self.doc, name="Harpy, Rail Harpy v3", role="DPS", srp_level=srp, fitting_text=FIT)
        fittings.store(ship)  # the types are in the table already, so no EVE call is made
        ship.save()
        self.ship = ship
        for tid, price in ((11381, 30e6), (2048, 1e6), (3074, 2e6), (12814, 100.0), (2456, 0.5e6)):
            TypePrice.objects.create(type_id=tid, sell_min=price)
        Insurance.objects.create(type_id=11381, cost=3e6, payout=10e6)

    def test_store_parsed_the_fitting(self):
        self.assertEqual((self.ship.ship_type_id, self.ship.ship_type_name, self.ship.parse_error), (11381, "Harpy", ""))
        self.assertEqual(self.ship.fitting_json["slots"]["high"][0]["charge"]["name"], "Spike S")

    def test_outsider_is_refused(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse("doctrines:index")).status_code, 302)  # permission_required sends to login

    def test_landing_lists_the_tile_under_its_category(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("doctrines:index"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Light &amp; cheap", html)
        self.assertNotIn(">APEX<", html)  # an empty category draws no row
        self.assertIn("Rail Harpies", html)
        self.assertIn("Home defense", html)
        self.assertIn("<li>bring what fits</li>", html)
        self.assertIn("types/11381/render", html)  # the tile shows the first ship

    def test_doctrine_page_costs_and_insures(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("doctrines:doctrine", args=[self.doc.slug]))
        self.assertEqual(r.status_code, 200)
        row = r.context["rows"][0]
        self.assertAlmostEqual(row["cost"]["hull"], 30e6)
        self.assertAlmostEqual(row["cost"]["fit"], 1e6 + 2e6 + 100.0)  # DC, gun, the loaded Spike
        self.assertAlmostEqual(row["cost"]["drones"], 1e6)
        self.assertAlmostEqual(row["cost"]["cargo"], 500 * 100.0)
        self.assertAlmostEqual(row["insurance"]["net"], 7e6)
        self.assertAlmostEqual(row["loss"], row["cost"]["total"] - 7e6)
        html = r.content.decode()
        self.assertIn("Full", html)
        self.assertIn("Copy fit to clipboard", html)
        self.assertIn("[Harpy, Rail Harpy v3]", html)
        self.assertIn("<ship-fit hide-copy>", html)  # the fitting wheel
        self.assertIn("vendor/shipfit.umd.min.js", html)

    def test_fit_text(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("doctrines:fit_text", args=[self.ship.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.decode().startswith("[Harpy, Rail Harpy v3]"))
        self.assertIn("Hobgoblin II x2", r.content.decode())

    def test_variants_group_under_one_hull(self):
        """Two fits of the same hull and role (T1 for low skills, T2 for full skills) make one row with two panes."""
        t1 = DoctrineShip(doctrine=self.doc, name="Harpy T1", role="DPS", variant="T1", order=1, fitting_text=FIT.replace("Damage Control II", "Damage Control I"))
        ItemType.objects.create(type_id=2046, name="Damage Control I", slot="low")
        TypePrice.objects.create(type_id=2046, sell_min=0.1e6)
        fittings.store(t1)
        t1.save()
        self.ship.variant = "T2"
        self.ship.order = 2
        self.ship.save()
        self.client.force_login(self.user)
        r = self.client.get(reverse("doctrines:doctrine", args=[self.doc.slug]))
        self.assertEqual(r.status_code, 200)
        groups = r.context["groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual((groups[0]["hull"], groups[0]["role"], groups[0]["multi"]), ("Harpy", "DPS", True))
        self.assertEqual([v["label"] for v in groups[0]["variants"]], ["T1", "T2"])
        self.assertLess(groups[0]["variants"][0]["cost"]["total"], groups[0]["variants"][1]["cost"]["total"])
        self.assertEqual([(b["role"], len(b["hulls"])) for b in r.context["roles"]], [("DPS", 1)])
        html = r.content.decode()
        self.assertEqual(html.count("doctrines-role-row"), 1)
        self.assertEqual(html.count("doctrines-ship-row"), 1)
        self.assertEqual(html.count("Copy fit to clipboard"), 2)
        self.assertEqual(html.count('class="nav-link doctrines-variant'), 2)
        self.assertIn("lower skills", html)
        self.assertIn("full skills", html)

    def test_srp_percent_tag_and_column(self):
        self.doc.srp_percent = 50
        self.doc.save()
        self.client.force_login(self.user)
        r = self.client.get(reverse("doctrines:doctrine", args=[self.doc.slug]))
        row = r.context["rows"][0]
        self.assertEqual(row["srp_percent"], 50)
        self.assertAlmostEqual(row["srp"], row["cost"]["total"] / 2)
        html = r.content.decode()
        self.assertIn("50 % SRP", html)
        self.assertIn('<span class="doctrines-srp-pct">50 %</span>', html)
        self.assertNotIn("Net insurance", html)
        self.assertIn("50 % SRP", self.client.get(reverse("doctrines:index")).content.decode())
        # a ship's own percentage wins (logistics at 100 %)
        self.ship.srp_percent = 100
        self.ship.save()
        r = self.client.get(reverse("doctrines:doctrine", args=[self.doc.slug]))
        self.assertEqual(r.context["rows"][0]["srp_percent"], 100)
        self.assertIn('<span class="doctrines-srp-pct is-full">100 %</span>', r.content.decode())

    def test_composition_chips_on_the_card(self):
        self.doc.composition = "DPS: 5\nLogistics: 3\nTackle: 1\nSupport: 1\nnot a number: x"
        self.doc.save()
        self.client.force_login(self.user)
        html = self.client.get(reverse("doctrines:doctrine", args=[self.doc.slug])).content.decode()
        self.assertEqual(html.count("doctrines-ratio-chip"), 4)
        self.assertIn("Logistics <strong>3</strong>", html)
        self.assertIn('<span class="doctrines-ratio-chip" data-role="logi">', html)
        self.assertIn("fa-kit-medical", html)

    def test_landing_bullets_with_a_keyword_become_tags(self):
        from ..models import SiteText

        SiteText.objects.update_or_create(defaults={"title": "How we Fly", "body": (
            "Pick a role:\n\n- DPS: the damage dealers\n- Logistics: keep the DPS alive\n- Scout: eyes ahead\n"
            "- Mind the rule: a sentence with a colon that is not a label at all\n- just a plain bullet")})
        self.client.force_login(self.user)
        html = self.client.get(reverse("doctrines:index")).content.decode()
        self.assertIn('<span class="doctrines-tag" data-role="dps"><i class="fas fa-crosshairs fa-fw" aria-hidden="true"></i>DPS</span>', html)
        self.assertIn('<span class="doctrines-tag" data-role="logi"><i class="fas fa-kit-medical fa-fw" aria-hidden="true"></i>Logistics</span>', html)
        self.assertIn('<span class="doctrines-tag" data-role="support"><i class="fas fa-eye fa-fw" aria-hidden="true"></i>Scout</span>', html)
        self.assertIn('<span class="doctrines-kv-text">keep the DPS alive</span>', html)
        self.assertIn("<li>Mind the rule: a sentence with a colon that is not a label at all</li>", html)  # keyword too long
        self.assertIn("<li>just a plain bullet</li>", html)
        self.assertIn('<ul class="doctrines-kv-list">', html)

    def test_strengths_show_keyword_and_description(self):
        self.doc.pros = "King of the hill - holds a point\nCheap: easy on the wallet\nJust a line"
        self.doc.save()
        self.client.force_login(self.user)
        html = self.client.get(reverse("doctrines:doctrine", args=[self.doc.slug])).content.decode()
        self.assertIn("<strong>King of the hill</strong>", html)
        self.assertIn("<strong>Cheap</strong>", html)
        self.assertIn("<li>Just a line</li>", html)

    def test_inactive_doctrine_is_hidden(self):
        self.doc.is_active = False
        self.doc.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("doctrines:doctrine", args=[self.doc.slug])).status_code, 404)
        self.assertNotIn("Rail Harpies", self.client.get(reverse("doctrines:index")).content.decode())
