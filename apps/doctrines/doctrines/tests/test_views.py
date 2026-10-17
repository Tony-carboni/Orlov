"""The pages: permission gate, landing tiles per category, a doctrine page with cost, insurance and SRP, the fit text."""
from allianceauth.tests.auth_utils import AuthUtils
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from ..models import Category, Doctrine, DoctrineShip, Insurance, ItemType, SiteText, SrpLevel, TypePrice
from ..services import fittings

FIT = "[Harpy, Rail Harpy v3]\nDamage Control II\n150mm Railgun II, Spike S\nHobgoblin II x2\nSpike S x500\n"


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

    def test_fit_text(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("doctrines:fit_text", args=[self.ship.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.decode().startswith("[Harpy, Rail Harpy v3]"))
        self.assertIn("Hobgoblin II x2", r.content.decode())

    def test_inactive_doctrine_is_hidden(self):
        self.doc.is_active = False
        self.doc.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("doctrines:doctrine", args=[self.doc.slug])).status_code, 404)
        self.assertNotIn("Rail Harpies", self.client.get(reverse("doctrines:index")).content.decode())
