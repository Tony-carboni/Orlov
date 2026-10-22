"""The LP log (0.25.0): readings become changes, the summary, the page."""
import datetime as dt
from unittest import mock

from allianceauth.tests.auth_utils import AuthUtils
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import LpSnapshot
from ..services import lplog


def _t(hour, day=22):
    return dt.datetime(2026, 10, day, hour, 0, tzinfo=dt.timezone.utc)


class RecordTests(TestCase):
    def test_first_reading_then_only_changes(self):
        self.assertEqual(lplog.record(1001, "Alice", {1000035: 8000, 1000180: 50000}, now=_t(9)), 2)
        first = LpSnapshot.objects.filter(character_id=1001)
        self.assertTrue(all(r.is_first and r.change == 0 for r in first))
        # nothing moved: nothing written
        self.assertEqual(lplog.record(1001, "Alice", {1000035: 8000, 1000180: 50000}, now=_t(10)), 0)
        # earned with the navy, spent with the militia, a new corporation appears
        self.assertEqual(lplog.record(1001, "Alice", {1000035: 9500, 1000180: 44000, 1000120: 300}, now=_t(11)), 3)
        rows = {r.corporation_id: r for r in LpSnapshot.objects.filter(character_id=1001, taken_at=_t(11))}
        self.assertEqual((rows[1000035].change, rows[1000035].loyalty_points, rows[1000035].previous_at), (1500, 9500, _t(9)))
        self.assertEqual((rows[1000180].change, rows[1000180].previous_at), (-6000, _t(9)))
        self.assertEqual((rows[1000120].change, rows[1000120].previous_at, rows[1000120].is_first), (300, _t(9), False))
        # a corporation vanishing from ESI is a fall to zero
        self.assertEqual(lplog.record(1001, "Alice", {1000035: 9500, 1000180: 44000}, now=_t(12)), 1)
        gone = LpSnapshot.objects.get(character_id=1001, taken_at=_t(12))
        self.assertEqual((gone.corporation_id, gone.loyalty_points, gone.change), (1000120, 0, -300))
        self.assertEqual(lplog.latest(1001)[1000120], (0, _t(12)))

    def test_snapshot_reads_every_token_and_logs(self):
        tok = mock.Mock(character_id=1001, character_name="Alice")
        with mock.patch.object(lplog, "tokens", return_value={1001: tok}), \
             mock.patch.object(lplog, "read", return_value={1000035: 8000}), \
             mock.patch.object(lplog, "polite_pause"), mock.patch.object(lplog, "resolve_corporation_names", return_value=0):
            result = lplog.snapshot()
        self.assertEqual((result["characters"], result["read"], result["written"], result["errors"]), (1, 1, 1, []))
        with mock.patch.object(lplog, "tokens", return_value={1001: tok}), \
             mock.patch.object(lplog, "read", side_effect=RuntimeError("esi down")), \
             mock.patch.object(lplog, "polite_pause"), mock.patch.object(lplog, "resolve_corporation_names", return_value=0):
            result = lplog.snapshot()
        self.assertEqual((result["read"], result["written"]), (0, 0))
        self.assertIn("esi down", result["errors"][0])


class SummaryTests(TestCase):
    def setUp(self):
        lplog.record(1001, "Alice", {1000035: 8000, 1000180: 50000}, now=_t(9))
        lplog.record(1002, "Bob", {1000180: 1000}, now=_t(9))
        lplog.record(1001, "Alice", {1000035: 9500, 1000180: 44000}, now=_t(11))
        lplog.record(1002, "Bob", {1000180: 4000}, now=_t(11, day=23))
        LpSnapshot.objects.filter(corporation_id=1000035).update(corporation_name="Caldari Navy")
        LpSnapshot.objects.filter(corporation_id=1000180).update(corporation_name="State Protectorate")

    def test_log_balances_and_summary(self):
        rows = lplog.log([1001, 1002])
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["character"], "Bob")  # newest first
        self.assertEqual(sorted(r["change"] for r in rows if r["character"] == "Alice" and not r["first"]), [-6000, 1500])
        bal = lplog.balances([1001, 1002])
        self.assertEqual((bal[1000180]["lp"], bal[1000180]["characters"], bal[1000035]["lp"]), (48000, 2, 9500))
        s = lplog.summary(rows, "day", bal)
        by = {c["corporation"]: c for c in s["corporations"]}
        self.assertEqual((by["State Protectorate"]["earned"], by["State Protectorate"]["spent"], by["State Protectorate"]["net"], by["State Protectorate"]["balance"]), (3000, 6000, -3000, 48000))
        self.assertEqual((by["Caldari Navy"]["earned"], by["Caldari Navy"]["balance"]), (1500, 9500))
        self.assertEqual((s["earned"], s["spent"], s["changes"]), (4500, 6000, 3))
        self.assertEqual(s["chart"]["labels"], ["2026-10-22", "2026-10-23"])
        labels = {d["label"]: d["data"] for d in s["chart"]["datasets"]}
        self.assertEqual(labels["State Protectorate spent"], [-6000, 0])
        self.assertEqual(labels["State Protectorate earned"], [0, 3000])
        only = lplog.log([1001], corporation_id=1000035)
        self.assertEqual({r["corporation_id"] for r in only}, {1000035})
        self.assertEqual(lplog.log([1001], since=_t(10)), [r for r in lplog.log([1001]) if r["at"] >= _t(10)])


@override_settings(SHIPYARD_STANDALONE_HOST="", STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PageTests(TestCase):
    def setUp(self):
        self.user = AuthUtils.create_user("logger")
        AuthUtils.add_main_character_2(self.user, "Alice", 1001, corp_id=2001, corp_name="Corp", corp_ticker="CORP")
        self.user = AuthUtils.add_permission_to_user_by_name("shipyard.basic_access", self.user)
        from allianceauth.authentication.models import CharacterOwnership
        from allianceauth.eveonline.models import EveCharacter
        CharacterOwnership.objects.get_or_create(character=EveCharacter.objects.get(character_id=1001), user=self.user, defaults={"owner_hash": "alice"})
        lplog.record(1001, "Alice", {1000035: 8000}, now=_t(9))
        lplog.record(1001, "Alice", {1000035: 9500}, now=_t(11))
        lplog.record(1002, "Bob", {1000035: 100}, now=_t(9))
        LpSnapshot.objects.update(corporation_name="Caldari Navy")

    def test_page_shows_my_characters_only_unless_allowed(self):
        self.client.force_login(self.user)
        with mock.patch.object(lplog, "tokens", return_value={}):
            r = self.client.get(reverse("shipyard:lplog"), {"days": 0})
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Caldari Navy", html)
        self.assertIn("+1,500", html)
        self.assertNotIn("Bob", html)
        with mock.patch.object(lplog, "tokens", return_value={}):
            r = self.client.get(reverse("shipyard:lplog"), {"days": 0, "who": "all"})
        self.assertNotIn("Bob", r.content.decode())  # not a manager: "all" falls back to me
        self.user = AuthUtils.add_permission_to_user_by_name("shipyard.manage_shipyard", self.user)
        self.client.force_login(self.user)
        with mock.patch.object(lplog, "tokens", return_value={}):
            r = self.client.get(reverse("shipyard:lplog"), {"days": 0, "who": "all"})
        self.assertIn("Bob", r.content.decode())
