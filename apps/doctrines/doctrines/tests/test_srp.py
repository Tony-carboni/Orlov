"""SRP: the doctrine match, the request from a kill, duplicates, the wallet matcher and the page's gate."""
from unittest import mock

from allianceauth.tests.auth_utils import AuthUtils
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import Category, Doctrine, DoctrineShip, ItemType, SrpRequest, TypePrice
from ..services import fittings, srp

FIT_T2 = "[Harpy, Harpy T2]\nDamage Control II\n150mm Railgun II, Spike S\n150mm Railgun II, Spike S\nHobgoblin II x2\n"
FIT_T1 = "[Harpy, Harpy T1]\nDamage Control I\n150mm Railgun II, Spike S\n150mm Railgun II, Spike S\n"


def killmail(ship_type_id=11381, items=None, alliance_id=99015337, character_id=1001):
    items = items if items is not None else [
        {"item_type_id": 2048, "flag": 11, "quantity_destroyed": 1},
        {"item_type_id": 3074, "flag": 27, "quantity_destroyed": 1},
        {"item_type_id": 3074, "flag": 28, "quantity_dropped": 1},
        {"item_type_id": 12814, "flag": 27, "quantity_destroyed": 1},   # the loaded charge, not a module
        {"item_type_id": 28668, "flag": 5, "quantity_dropped": 50},     # cargo
    ]
    return {
        "killmail_id": 139000001, "killmail_time": "2026-10-17T21:03:00Z", "solar_system_id": 30002813,
        "victim": {"character_id": character_id, "corporation_id": 98843356, "alliance_id": alliance_id, "ship_type_id": ship_type_id, "items": items},
        "attackers": [], "zkb": {"hash": "abc", "totalValue": 99e6, "fittedValue": 40e6},
    }


NAMES = {1001: "Reader Main", 98843356: "Orlov Arms International", 99015337: "The Orlov Family", 11381: "Harpy", 30002813: "Piekura", 2048: "Damage Control II", 2046: "Damage Control I", 3074: "150mm Railgun II"}


@override_settings(DOCTRINES_HOST="", DOCTRINES_SRP_ALLIANCE_IDS=[99015337])
class SrpTests(TestCase):
    def setUp(self):
        for tid, name, slot in ((11381, "Harpy", "ship"), (2048, "Damage Control II", "low"), (2046, "Damage Control I", "low"),
                                (3074, "150mm Railgun II", "high"), (12814, "Spike S", "charge"), (2456, "Hobgoblin II", "drone")):
            ItemType.objects.create(type_id=tid, name=name, slot=slot)
        for tid, price in ((11381, 30e6), (2048, 1e6), (2046, 0.1e6), (3074, 2e6), (12814, 100.0), (2456, 0.5e6)):
            TypePrice.objects.create(type_id=tid, sell_min=price)
        cat = Category.objects.create(name="Light & cheap", order=1)
        self.doc = Doctrine.objects.create(category=cat, name="Rail Harpies", gameplay="Home defense", srp_percent=50)
        self.t2 = DoctrineShip(doctrine=self.doc, name="Harpy T2", role="DPS", variant="T2", order=1, fitting_text=FIT_T2)
        fittings.store(self.t2); self.t2.save()
        self.t1 = DoctrineShip(doctrine=self.doc, name="Harpy T1", role="DPS", variant="T1", order=1, fitting_text=FIT_T1)
        fittings.store(self.t1); self.t1.save()
        self.agent = AuthUtils.create_user("agent")
        AuthUtils.add_main_character_2(self.agent, "Agent Main", 1002, corp_id=98843356, corp_name="OARMI", corp_ticker="OARMI")
        self.agent = AuthUtils.add_permission_to_user_by_name("doctrines.basic_access", self.agent)
        self.agent = AuthUtils.add_permission_to_user_by_name("doctrines.srp_agent", self.agent)
        self.reader = AuthUtils.create_user("reader")
        self.reader = AuthUtils.add_permission_to_user_by_name("doctrines.basic_access", self.reader)

    def test_kill_id_from_link_or_number(self):
        self.assertEqual(srp.kill_id_from("https://zkillboard.com/kill/139051327/"), 139051327)
        self.assertEqual(srp.kill_id_from(" 139051327 "), 139051327)
        self.assertIsNone(srp.kill_id_from("hello"))

    def test_match_picks_the_fit_whose_modules_were_fitted(self):
        fitted = srp.fitted_type_ids(killmail()["victim"])
        self.assertEqual(sorted(fitted), [2048, 3074, 3074, 12814])  # charges in a gun slot carry the slot flag too; they just never match a module
        ship, score, missing = srp.match(11381, fitted)
        self.assertEqual((ship.pk, score, dict(missing)), (self.t2.pk, 1.0, {}))
        ship, score, missing = srp.match(11381, [2046, 3074])
        self.assertEqual((ship.pk, dict(missing)), (self.t1.pk, {3074: 1}))
        self.assertAlmostEqual(score, 2 / 3)
        self.assertEqual(srp.match(587, [2048])[0], None)

    @mock.patch.object(srp, "names_of", side_effect=lambda ids: {i: NAMES.get(i, "") for i in ids})
    @mock.patch.object(srp, "fetch_kill", return_value=killmail())
    def test_request_from_a_doctrine_loss_is_open_with_the_doctrine_payout(self, _fetch, _names):
        record, created = srp.create_from_kill(139000001, requested_by="Reader", discord_id=42, message_id=7)
        self.assertTrue(created)
        self.assertEqual((record.status, record.adhoc, record.doctrine_ship_id, record.pilot_name, record.ship_type_name, record.system_name), ("open", False, self.t2.pk, "Reader Main", "Harpy", "Piekura"))
        cost = fittings.page_data([self.t2], 50)[0]["cost"]["total"]
        self.assertEqual(record.payout, round(cost / 2))
        self.assertEqual(record.srp_percent, 50)
        self.assertAlmostEqual(record.zkb_value, 99e6)
        # the same kill again: no second request
        again, created = srp.create_from_kill(139000001, requested_by="Someone else")
        self.assertFalse(created)
        self.assertEqual(again.pk, record.pk)
        self.assertEqual(SrpRequest.objects.count(), 1)

    @mock.patch.object(srp, "names_of", side_effect=lambda ids: {i: NAMES.get(i, "") for i in ids})
    def test_non_doctrine_fit_and_unknown_hull_are_ad_hoc(self, _names):
        with mock.patch.object(srp, "fetch_kill", return_value=killmail(items=[{"item_type_id": 2046, "flag": 11, "quantity_destroyed": 1}])):
            record, _ = srp.create_from_kill(139000002)
        self.assertEqual((record.status, record.adhoc, record.doctrine_ship_id), ("review", True, self.t1.pk))
        self.assertIn("2 doctrine module(s) not fitted: 2 × 150mm Railgun II", record.adhoc_reason)  # the T1 fit matched best: its DC I was fitted, the guns were not
        self.assertIsNotNone(record.payout)  # the doctrine figure as the suggestion
        with mock.patch.object(srp, "fetch_kill", return_value=killmail(ship_type_id=587)):
            record, _ = srp.create_from_kill(139000003)
        self.assertEqual((record.status, record.doctrine_ship_id, record.payout), ("review", None, None))
        self.assertIn("no active doctrine carries", record.adhoc_reason)
        with mock.patch.object(srp, "fetch_kill", return_value=killmail(alliance_id=1)):
            record, _ = srp.create_from_kill(139000004)
        self.assertIn("not in the alliance", record.adhoc_reason)

    @mock.patch.object(srp, "names_of", side_effect=lambda ids: {i: NAMES.get(i, "") for i in ids})
    @mock.patch.object(srp, "fetch_kill", return_value=killmail())
    def test_wallet_matcher_marks_paid_by_kill_id_in_the_reason(self, _fetch, _names):
        record, _ = srp.create_from_kill(139000001)
        journal = [
            {"id": 1, "amount": 5e6, "ref_type": "player_donation", "reason": "139000001", "date": "2026-10-18T10:00:00Z"},   # money in, ignored
            {"id": 2, "amount": -record.payout, "ref_type": "corporation_account_withdrawal", "reason": "SRP 139000001", "date": "2026-10-18T10:05:00Z"},
            {"id": 3, "amount": -1e6, "ref_type": "corporation_account_withdrawal", "reason": "139999999", "date": "2026-10-18T10:06:00Z"},  # unknown kill
        ]
        result = srp.match_payments(journal)
        self.assertEqual(result["matched"], 1)
        record.refresh_from_db()
        self.assertEqual((record.status, record.paid_journal_id, record.paid_amount), ("paid", 2, float(record.payout)))
        self.assertEqual(srp.match_payments(journal)["matched"], 0)  # nothing left to match

    def test_page_is_for_agents_only(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(reverse("doctrines:srp")).status_code, 302)
        self.client.force_login(self.agent)
        r = self.client.get(reverse("doctrines:srp"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("SRP requests", r.content.decode())

    @mock.patch.object(srp, "names_of", side_effect=lambda ids: {i: NAMES.get(i, "") for i in ids})
    @mock.patch.object(srp, "fetch_kill", return_value=killmail())
    def test_agent_adds_by_hand_and_marks_paid(self, _fetch, _names):
        self.client.force_login(self.agent)
        r = self.client.post(reverse("doctrines:srp_add"), {"kill": "https://zkillboard.com/kill/139000001/"})
        self.assertEqual(r.status_code, 302)
        record = SrpRequest.objects.get(kill_id=139000001)
        self.assertEqual((record.source, record.requested_by), ("manual", "agent"))
        html = self.client.get(reverse("doctrines:srp")).content.decode()
        self.assertIn('data-text="Reader Main"', html)
        self.assertIn('data-text="139000001"', html)
        self.assertIn(f'data-text="{record.payout:.0f}"', html)
        self.client.post(reverse("doctrines:srp_action", args=[record.pk]), {"action": "paid"})
        record.refresh_from_db()
        self.assertEqual((record.status, record.paid_amount, record.reviewed_by), ("paid", float(record.payout), "agent"))
        self.client.post(reverse("doctrines:srp_action", args=[record.pk]), {"action": "reopen"})
        record.refresh_from_db()
        self.assertEqual(record.status, "open")
