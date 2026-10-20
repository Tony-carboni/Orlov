"""Member shipyards: the owner's preview of the dashboard as a new member sees it."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import (
    BuildSnapshot, Facility, MarketLocation, MaterialType, MemberBlueprintPrice, PriceSnapshot, Ship, ShipConfig,
    ShipMarketStats,
)
from ..services import board


@override_settings(SHIPYARD_STANDALONE_HOST="")
class MemberViewTests(TestCase):
    def setUp(self):
        from allianceauth.tests.auth_utils import AuthUtils
        self.owner = get_user_model().objects.create_user("tony", password="x")
        AuthUtils.add_main_character_2(self.owner, "Tony Main", 9001, corp_id=9002, corp_name="Corp", alliance_id=None, alliance_name="")
        for codename in ("basic_access", "manage_shipyard"):
            self.owner.user_permissions.add(Permission.objects.get(codename=codename, content_type__app_label="shipyard"))
        self.member = get_user_model().objects.create_user("member", password="x")
        AuthUtils.add_main_character_2(self.member, "Member Main", 9003, corp_id=9002, corp_name="Corp", alliance_id=None, alliance_name="")
        self.member.user_permissions.add(Permission.objects.get(codename="basic_access", content_type__app_label="shipyard"))
        self.fac = Facility.objects.create(name="Raitaru", structure_type_id=35825, structure_name="Raitaru",
                                           system_id=30001387, system_name="Isikano", rig_type_ids=[43732], is_default=True)
        self.other = Facility.objects.create(name="Piekura public", structure_type_id=35825, structure_name="Raitaru",
                                             system_id=30001391, system_name="Piekura", rig_type_ids=[])
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
        # the owner's own rules: no markup, a tax override, his own price for the copy
        s = board.get_user_settings(self.owner)
        s.bpc_markup = 0
        s.manual_sales_tax = 1.5
        s.save()
        MemberBlueprintPrice.objects.create(user=self.owner, ship=self.ship, price_isk=5_000_000)

    def test_member_settings_ignore_the_owner(self):
        m = board.member_settings()
        self.assertIsNone(m.pk)
        self.assertIsNone(m.user_id)
        self.assertIsNone(m.markup_fraction)
        self.assertIsNone(m.manual_sales_tax)
        self.assertEqual((m.facility, m.market), (self.fac, self.market))
        self.assertEqual(board.member_settings(self.other).facility, self.other)
        owner_row = board.dashboard_rows(board.get_user_settings(self.owner))[0]
        member_row = board.dashboard_rows(m)[0]
        self.assertEqual(owner_row.econ.bpc_source, "own")
        self.assertNotEqual(member_row.econ.bpc_source, "own")
        self.assertIsNone(member_row.own_price)

    def test_page_for_the_owner_only_and_saves_nothing(self):
        client = Client()
        client.force_login(self.member)
        self.assertNotEqual(client.get(reverse("shipyard:member")).status_code, 200)
        client.force_login(self.owner)
        r = client.get(reverse("shipyard:member"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Member shipyards", html)
        self.assertIn(reverse("shipyard:member_ship", args=[self.ship.type_id]), html)
        self.assertNotIn('id="bpc-price"', html)  # no own-price form in the preview
        self.assertIn('data-storage-prefix="member."', html)
        # another facility is a preview only
        r = client.get(reverse("shipyard:member") + f"?facility={self.other.pk}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["settings"].facility, self.other)
        s = board.get_user_settings(self.owner)
        self.assertEqual((s.facility, float(s.bpc_markup), float(s.manual_sales_tax)), (self.fac, 0.0, 1.5))
        self.assertEqual(MemberBlueprintPrice.objects.filter(user=self.owner).count(), 1)
        # the ship page of the preview
        r = client.get(reverse("shipyard:member_ship", args=[self.ship.type_id]))
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.context["econ"].bpc_source, "own")
        self.assertIn("?as=member", r.content.decode())
        # the owner's own dashboard is unchanged and links to the preview in the nav
        r = client.get(reverse("shipyard:index"))
        self.assertEqual(r.context["rows"][0].econ.bpc_source, "own")
        self.assertIn(reverse("shipyard:member"), r.content.decode())
