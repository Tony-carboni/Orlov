"""LP conversion (0.15.0): offers from ESI, the table's maths, the blueprint target price, the page."""
from unittest import mock

from allianceauth.tests.auth_utils import AuthUtils
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ..models import LpOffer, LpTypeMarket, MarketLocation, MaterialType
from ..services import lpstore

STORE = 1000180
NOW = timezone.now()


def market(tid, name, sell=None, volume=0.0, orders=0, daily=0.0, bpc=False):
    return LpTypeMarket.objects.create(type_id=tid, name=name, is_blueprint=bpc, sell_min=sell, sell_volume=volume, sell_orders=orders,
                                       avg_daily_volume=daily, prices_at=NOW, volume_at=NOW)


class RowTests(TestCase):
    def setUp(self):
        market(3895, "Caldari Navy Antimatter Charge M", sell=1_000.0, volume=50_000, orders=20, daily=10_000)
        market(17703, "Caldari Navy Hookbill", sell=25_000_000.0, volume=40, orders=8, daily=20)
        market(17704, "Caldari Navy Hookbill Blueprint", bpc=True)
        market(12806, "Caldari Navy Hookbill (input)", sell=None)
        market(17706, "Scorpion Navy Issue", sell=400_000_000.0, volume=10, orders=5, daily=4)
        market(17705, "Scorpion", sell=100_000_000.0)
        # 5,000 charges for 1,000 LP and 1 M ISK
        LpOffer.objects.create(store_corp_id=STORE, offer_id=1, type_id=3895, quantity=5000, lp_cost=1000, isk_cost=1_000_000, fetched_at=NOW)
        # a navy ship for 100,000 LP + 50 M, handing in the base hull
        LpOffer.objects.create(store_corp_id=STORE, offer_id=2, type_id=17706, quantity=1, lp_cost=100_000, isk_cost=50_000_000,
                               required_items=[[17705, 1]], fetched_at=NOW)
        # a blueprint copy for 10,000 LP + 10 M
        LpOffer.objects.create(store_corp_id=STORE, offer_id=3, type_id=17704, quantity=1, lp_cost=10_000, isk_cost=10_000_000, fetched_at=NOW)
        # an offer whose input has no Jita price
        LpOffer.objects.create(store_corp_id=STORE, offer_id=4, type_id=17703, quantity=1, lp_cost=5_000, isk_cost=0,
                               required_items=[[12806, 2]], fetched_at=NOW)
        LpOffer.objects.create(store_corp_id=STORE, offer_id=9, type_id=3895, quantity=1, lp_cost=1, isk_cost=0, fetched_at=NOW, is_active=False)

    @override_settings(SHIPYARD_LP_TARGET_ISK_PER_LP=900)
    def test_net_rate_inputs_depth_and_blueprint_target(self):
        rows = {r.offer_id: r for r in lpstore.rows(fees=0.05)}
        self.assertEqual(set(rows), {1, 2, 3, 4})  # the inactive offer is left out
        charges = rows[1]
        self.assertAlmostEqual(charges.output_value, 5_000_000)
        self.assertAlmostEqual(charges.net, 4_000_000)
        self.assertAlmostEqual(charges.isk_per_lp, 4_000)
        self.assertAlmostEqual(charges.isk_per_lp_after, (5_000_000 * 0.95 - 1_000_000) / 1000)
        self.assertAlmostEqual(charges.depth_days, 5.0)
        ship = rows[2]
        self.assertEqual([(n, q, c) for _, n, q, _, c in ship.inputs], [("Scorpion", 1, 100_000_000.0)])
        self.assertAlmostEqual(ship.net, 400e6 - 50e6 - 100e6)
        self.assertAlmostEqual(ship.isk_per_lp, 2_500)
        bpc = rows[3]
        self.assertTrue(bpc.is_blueprint)
        self.assertIsNone(bpc.isk_per_lp)
        self.assertAlmostEqual(bpc.bpc_target, 900 * 10_000 + 10_000_000)
        self.assertAlmostEqual(bpc.bpc_target_after, (900 * 10_000 + 10_000_000) / 0.95)
        hook = rows[4]
        self.assertFalse(hook.inputs_complete)
        self.assertAlmostEqual(hook.isk_per_lp, 25_000_000 / 5_000)  # the unpriced input costs nothing in the figure, flagged on the page
        self.assertEqual([r.offer_id for r in lpstore.rows()][:2], [1, 2])  # best rate first, blueprints last


class RefreshTests(TestCase):
    def test_offers_are_stored_named_and_retired(self):
        MarketLocation.objects.create(name="Jita", station_id=60003760, is_default=True)
        MaterialType.objects.create(type_id=17704, name="Caldari Navy Hookbill Blueprint")
        MaterialType.objects.create(type_id=3895, name="Caldari Navy Antimatter Charge M")
        MaterialType.objects.create(type_id=17705, name="Scorpion")
        LpOffer.objects.create(store_corp_id=STORE, offer_id=77, type_id=3895, quantity=1, lp_cost=1, isk_cost=0, fetched_at=NOW)
        payload = [
            {"offer_id": 1, "type_id": 3895, "quantity": 5000, "lp_cost": 1000, "isk_cost": 1000000, "ak_cost": 0, "required_items": []},
            {"offer_id": 3, "type_id": 17704, "quantity": 1, "lp_cost": 10000, "isk_cost": 10000000, "ak_cost": 0,
             "required_items": [{"type_id": 17705, "quantity": 1}]},
        ]
        with mock.patch.object(lpstore, "get_json", return_value=payload), mock.patch.object(lpstore, "ensure_type_names"):
            result = lpstore.refresh_offers()
        self.assertEqual(result, {"offers": 2, "gone": 1, "types": 3})
        self.assertFalse(LpOffer.objects.get(offer_id=77).is_active)
        self.assertEqual(LpOffer.objects.get(offer_id=3).required_items, [[17705, 1]])
        self.assertTrue(LpTypeMarket.objects.get(type_id=17704).is_blueprint)
        self.assertFalse(LpTypeMarket.objects.get(type_id=17705).is_blueprint)
        agg = {3895: {"sell_min": 1000.0, "sell_percentile": 1010.0, "sell_volume": 50000.0, "sell_orders": 20, "buy_max": 900.0}}
        with mock.patch.object(lpstore.fuzzwork, "station_aggregates", return_value=agg):
            self.assertEqual(lpstore.refresh_prices(), {"types": 1})
        self.assertEqual(LpTypeMarket.objects.get(type_id=3895).sell_volume, 50000.0)
        with mock.patch.object(lpstore.esi, "volume_stats", return_value={"avg_daily_volume": 12.5, "avg_price": 1.0, "days": 7}), \
             mock.patch.object(lpstore, "polite_pause"):
            result = lpstore.refresh_volumes()
        self.assertEqual(result["types"], 1)  # the blueprint is skipped
        self.assertEqual(LpTypeMarket.objects.get(type_id=3895).avg_daily_volume, 12.5)


@override_settings(SHIPYARD_STANDALONE_HOST="")
class PageTests(TestCase):
    def setUp(self):
        self.user = AuthUtils.create_user("trader")
        AuthUtils.add_main_character_2(self.user, "Trader Main", 1001, corp_id=2001, corp_name="Corp", corp_ticker="CORP")
        self.user = AuthUtils.add_permission_to_user_by_name("shipyard.basic_access", self.user)
        market(3895, "Caldari Navy Antimatter Charge M", sell=1_000.0, volume=50_000, orders=20, daily=10_000)
        market(17704, "Caldari Navy Hookbill Blueprint", bpc=True)
        LpOffer.objects.create(store_corp_id=STORE, offer_id=1, type_id=3895, quantity=5000, lp_cost=1000, isk_cost=1_000_000, fetched_at=NOW)
        LpOffer.objects.create(store_corp_id=STORE, offer_id=3, type_id=17704, quantity=1, lp_cost=10_000, isk_cost=10_000_000, fetched_at=NOW)

    def test_page_lists_offers_and_the_blueprint_target(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("shipyard:lp"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Caldari Navy Antimatter Charge M", html)
        self.assertIn('data-kind="blueprint"', html)
        self.assertIn("BPC @ 900", html)
        self.assertIn("19.0 M", html)  # 900 × 10,000 + 10 M
        self.assertIn("LP conversion", html)  # the nav entry

    def test_refresh_needs_the_manager_permission(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("shipyard:lp_refresh")).status_code, 302)  # sent to login by permission_required
        self.user = AuthUtils.add_permission_to_user_by_name("shipyard.manage_shipyard", self.user)
        with mock.patch("shipyard.tasks.refresh_lp_store.delay") as delay:
            r = self.client.post(reverse("shipyard:lp_refresh"))
        self.assertRedirects(r, reverse("shipyard:lp"), fetch_redirect_response=False)
        delay.assert_called_once()
