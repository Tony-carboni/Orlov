from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import (
    BuildSnapshot, Facility, MarketLocation, MaterialType, MemberBlueprintPrice, PriceSnapshot, Ship, ShipConfig,
    ShipMarketStats,
)
from ..services import board


class BoardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tony", password="x")
        # Alliance Auth lets only users with a main character into app pages
        from allianceauth.tests.auth_utils import AuthUtils
        AuthUtils.add_main_character_2(self.user, "Tony Main", 9001, corp_id=9002, corp_name="Corp", alliance_id=None, alliance_name="")
        self.fac = Facility.objects.create(name="Raitaru", structure_type_id=35825, structure_name="Raitaru",
                                           system_id=30001387, system_name="Isikano", rig_type_ids=[43732], is_default=True)
        self.market = MarketLocation.objects.create(name="Jita", station_id=60003760, is_default=True)
        self.ship = Ship.objects.create(type_id=17740, name="Vindicator", group_id=27, hull_size="Battleship",
                                        category="Pirate", faction_id=500020, blueprint_type_id=17741)
        ShipConfig.objects.create(ship=self.ship, bpc_price_isk=23_000_000)
        MaterialType.objects.create(type_id=34, name="Tritanium", volume=0.01)
        BuildSnapshot.objects.create(ship=self.ship, facility=self.fac, me=0,
                                     materials=[{"type_id": 34, "quantity": 1000}], job_cost=17_985_640, time_seconds=8323)
        PriceSnapshot.objects.create(type_id=34, location=self.market, sell_min=818_135.38, sell_volume=1e9)
        PriceSnapshot.objects.create(type_id=17740, location=self.market, sell_min=999_900_000, sell_volume=53)
        ShipMarketStats.objects.create(ship=self.ship, avg_daily_volume=7.57)

    def test_set_facility_from_the_dashboard(self):
        from django.contrib.auth.models import Permission
        from django.test import Client, override_settings
        from django.urls import reverse
        other = Facility.objects.create(name="Piekura public", structure_type_id=35825, structure_name="Raitaru",
                                        system_id=30001391, system_name="Piekura", rig_type_ids=[])
        self.user.user_permissions.add(Permission.objects.get(codename="basic_access", content_type__app_label="shipyard"))
        client = Client()
        client.force_login(self.user)
        # the front door may be switched on where the tests run; keep this test on auth's own host
        with override_settings(SHIPYARD_STANDALONE_HOST=""):
            response = client.post(reverse("shipyard:set_facility", args=[other.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(board.get_user_settings(self.user).facility, other)
        # GET is not allowed, an inactive facility is a 404
        with override_settings(SHIPYARD_STANDALONE_HOST=""):
            self.assertEqual(client.get(reverse("shipyard:set_facility", args=[other.pk])).status_code, 405)
            other.is_active = False
            other.save()
            self.assertEqual(client.post(reverse("shipyard:set_facility", args=[other.pk])).status_code, 404)

    def test_own_blueprint_price(self):
        from django.contrib.auth.models import Permission
        from django.test import Client, override_settings
        from django.urls import reverse
        s = board.get_user_settings(self.user)
        s.manual_sales_tax = 4.81
        s.manual_broker_fee = 0
        s.save()
        # the member typed 23 M for the Vindicator copy: it replaces "Price not known"
        MemberBlueprintPrice.objects.create(user=self.user, ship=self.ship, price_isk=23_000_000)
        rows = board.dashboard_rows(s)
        e = rows[0].econ
        self.assertEqual(e.bpc_source, "own")
        self.assertFalse(e.bpc_excluded)
        self.assertAlmostEqual(e.bpc_cost, 23_000_000.0)
        self.assertAlmostEqual(e.net_profit, 92_683_787.9, delta=10)
        self.assertEqual(rows[0].own_price, 23_000_000.0)
        # the detail page follows, unless the simulation types another price
        self.assertEqual(board.ship_detail(self.ship, s)["econ"].bpc_source, "own")
        self.assertEqual(board.ship_detail(self.ship, s, bpc=1)["econ"].bpc_cost, 1.0)
        # the right-click form: set, change, clear; only active ships
        self.user.user_permissions.add(Permission.objects.get(codename="basic_access", content_type__app_label="shipyard"))
        client = Client()
        client.force_login(self.user)
        with override_settings(SHIPYARD_STANDALONE_HOST=""):
            url = reverse("shipyard:set_bpc_price", args=[self.ship.type_id])
            self.assertEqual(client.post(url, {"price": "25,000,000"}).status_code, 302)
            self.assertEqual(float(MemberBlueprintPrice.objects.get(user=self.user, ship=self.ship).price_isk), 25_000_000.0)
            self.assertEqual(client.post(url, {"price": ""}).status_code, 302)
            self.assertFalse(MemberBlueprintPrice.objects.filter(user=self.user, ship=self.ship).exists())
            self.assertEqual(client.get(url).status_code, 405)
            self.assertEqual(client.post(reverse("shipyard:set_bpc_price", args=[999999]), {"price": "1"}).status_code, 404)
        self.assertEqual(board.dashboard_rows(s)[0].econ.bpc_source, "public")

    def test_settings_defaults(self):
        s = board.get_user_settings(self.user)
        self.assertEqual(s.facility, self.fac)
        self.assertEqual(s.market, self.market)

    def test_dashboard_rows(self):
        s = board.get_user_settings(self.user)
        s.manual_sales_tax = 4.81
        s.manual_broker_fee = 0
        s.save()
        rows = board.dashboard_rows(s)
        self.assertEqual(len(rows), 1)
        e = rows[0].econ
        # a pirate hull: the corp cannot supply the copy, so the typed 23 M blueprint is
        # left out of the cost and the profit is marked as "without blueprint"
        self.assertAlmostEqual(e.net_profit, 92_683_787.9 + 23_000_000, delta=10)
        self.assertTrue(e.bpc_excluded)
        self.assertEqual(e.bpc_source, "public")
        self.assertTrue(e.complete)
        self.assertAlmostEqual(e.market_depth_days, 7.0, places=1)

    def test_detail_uses_snapshot_for_me0_and_live_for_sim(self):
        s = board.get_user_settings(self.user)
        d = board.ship_detail(self.ship, s)
        self.assertEqual(d["source"], "snapshot")
        fake = {"materials": [{"type_id": 34, "quantity": 900}], "estimated_item_value": 1, "job_cost": 17_000_000,
                "system_cost_isk": 0, "scc_surcharge": 0, "facility_tax_isk": 0, "time_seconds": 8000, "materials_volume": 9}
        with mock.patch.object(board.everef, "manufacturing_cost", return_value={}), \
             mock.patch.object(board.everef, "normalise_cost_block", return_value=fake):
            d = board.ship_detail(self.ship, s, me=10)
        self.assertEqual(d["source"], "live")
        self.assertEqual(d["econ"].materials[0].quantity, 900)
        # the stored snapshot is untouched
        self.assertEqual(BuildSnapshot.objects.get(ship=self.ship).materials[0]["quantity"], 1000)

    def test_detail_bpc_override(self):
        s = board.get_user_settings(self.user)
        # pirate hull: no blueprint source by policy
        d = board.ship_detail(self.ship, s)
        self.assertEqual(d["econ"].bpc_cost, 0.0)
        self.assertTrue(d["econ"].bpc_excluded)
        # a typed price is a real quote and overrides the policy in the simulation
        d = board.ship_detail(self.ship, s, bpc=23_000_000)
        self.assertEqual(d["econ"].bpc_cost, 23_000_000.0)
        self.assertFalse(d["econ"].bpc_excluded)
        d = board.ship_detail(self.ship, s, bpc=0)
        self.assertEqual(d["econ"].bpc_cost, 0.0)
        self.assertFalse(d["econ"].bpc_excluded)
