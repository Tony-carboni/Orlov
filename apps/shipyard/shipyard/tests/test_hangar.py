"""The projects hangar (0.27.0): ESI rows aggregated, the read stored, the count narrowed by the settings."""
import datetime as dt
from unittest import mock

from django.test import TestCase, override_settings

from django.core.cache import cache

from ..models import HangarItem
from ..services import hangar


def _page(rows, expires="Sat, 24 Oct 2026 05:31:00 GMT"):
    """A fake ESI response: one page with an Expires header."""
    r = mock.Mock()
    r.json.return_value = rows
    r.headers = {"X-Pages": "1", "Expires": expires}
    return r

CID = 98843356
RAITARU = 1055528480464


class HangarTests(TestCase):
    def test_aggregate_keeps_corp_hangars_only(self):
        rows = [
            {"type_id": 62536, "quantity": 14406, "location_id": RAITARU, "location_flag": "CorpSAG2", "is_singleton": False},
            {"type_id": 62536, "quantity": 100, "location_id": RAITARU, "location_flag": "CorpSAG2", "is_singleton": False},
            {"type_id": 48112, "quantity": 600, "location_id": RAITARU, "location_flag": "CorpDeliveries", "is_singleton": False},
            {"type_id": 11184, "quantity": 1, "location_id": RAITARU, "location_flag": "Hangar", "is_singleton": True},       # a ship: not a corp hangar
            {"type_id": 35, "quantity": 5, "location_id": 60003760, "location_flag": "CorpSAG1", "is_singleton": False},
        ]
        self.assertEqual(hangar.aggregate(rows), {(62536, RAITARU, "CorpSAG2"): 14506, (48112, RAITARU, "CorpDeliveries"): 600, (35, 60003760, "CorpSAG1"): 5})

    def test_refresh_replaces_the_rows_and_stock_follows_the_settings(self):
        tok = mock.Mock(character_name="Catherine Frey")
        tok.valid_access_token.return_value = "x"
        rows = [
            {"type_id": 62536, "quantity": 14406, "location_id": RAITARU, "location_flag": "CorpSAG2"},
            {"type_id": 48112, "quantity": 600, "location_id": RAITARU, "location_flag": "CorpDeliveries"},
            {"type_id": 35, "quantity": 5, "location_id": 60003760, "location_flag": "CorpSAG1"},
            {"type_id": 62536, "quantity": 100, "location_id": RAITARU, "location_flag": "CorporationGoalDeliveries"},  # the game's Projects hangar
        ]
        with mock.patch.object(hangar, "token", return_value=tok), mock.patch.object(hangar.esi, "_authed", return_value=_page(rows)), \
             mock.patch.object(hangar.projects, "corp_id", return_value=CID), mock.patch("shipyard.services.projectbooks._names", return_value={62536: "Compressed Kernite"}):
            r = hangar.refresh()
        self.assertEqual((r["rows"], r["types"], r["character"]), (4, 3, "Catherine Frey"))
        self.assertEqual(HangarItem.objects.filter(corporation_id=CID).count(), 4)
        for name in ("SHIPYARD_BOOKS_HANGAR_LOCATIONS", "SHIPYARD_BOOKS_HANGAR_FLAGS"):  # the live settings pin the count to the real hangar
            patch = mock.patch.object(hangar.app_settings, name, [])
            patch.start()
            self.addCleanup(patch.stop)
        units, names, read_at = hangar.stock(CID)
        self.assertEqual(units, {62536: 100})  # no pin: the game's Projects hangar only (0.31.1)
        self.assertEqual(names[62536], "Compressed Kernite")
        self.assertIsNotNone(read_at)
        with override_settings(SHIPYARD_BOOKS_HANGAR_LOCATIONS=[RAITARU], SHIPYARD_BOOKS_HANGAR_FLAGS=["CorpSAG2"]):
            with mock.patch.object(hangar.app_settings, "SHIPYARD_BOOKS_HANGAR_LOCATIONS", [RAITARU]), mock.patch.object(hangar.app_settings, "SHIPYARD_BOOKS_HANGAR_FLAGS", ["CorpSAG2"]):
                units, _, _ = hangar.stock(CID)
                self.assertEqual(units, {62536: 14406})
                divs = hangar.divisions(CID)
        self.assertEqual([(d["flag"], d["wanted"]) for d in divs], [("CorpSAG1", False), ("CorpDeliveries", False), ("CorpSAG2", True), ("CorporationGoalDeliveries", False)])
        # a second read replaces everything
        with mock.patch.object(hangar, "token", return_value=tok), mock.patch.object(hangar.esi, "_authed", return_value=_page(rows[:1])), \
             mock.patch.object(hangar.projects, "corp_id", return_value=CID), mock.patch("shipyard.services.projectbooks._names", return_value={}):
            hangar.refresh()
        self.assertEqual(HangarItem.objects.filter(corporation_id=CID).count(), 1)

    def test_the_projects_hangar_follows_the_delivery_office_by_default(self):
        """0.28.0: with no pin in the settings, the hangar that counts is the office the projects deliver to (every hangar
        division there, not the deliveries hangar); goods moved to another structure are not goods held."""
        from ..models import CorpProject, HangarItem
        CorpProject.objects.create(project_id="px", corporation_id=CID, name="veldspar", state="Active",
                                   details={"configuration": {"deliver_item": {"items": [{"type_id": 62516}], "office_id": 1055911110036}}})
        for loc, flag, qty in ((1055911110036, "CorporationGoalDeliveries", 500), (1055911110036, "CorpSAG3", 300), (1055911110036, "CorpDeliveries", 7), (1055529310484, "CorpSAG2", 9000)):
            HangarItem.objects.create(corporation_id=CID, type_id=62516, name="Compressed Veldspar", quantity=qty, location_id=loc, location_flag=flag, read_at=dt.datetime(2026, 10, 23, 9, tzinfo=dt.timezone.utc))
        with mock.patch.object(hangar.app_settings, "SHIPYARD_BOOKS_HANGAR_LOCATIONS", []), mock.patch.object(hangar.app_settings, "SHIPYARD_BOOKS_HANGAR_FLAGS", []):
            self.assertEqual(hangar.project_offices(CID), {1055911110036})
            units, names, _ = hangar.stock(CID)
            self.assertEqual(units, {62516: 500})
            self.assertEqual([(d["location_id"], d["flag"], d["wanted"]) for d in hangar.divisions(CID)],
                             [(1055529310484, "CorpSAG2", False), (1055911110036, "CorpDeliveries", False), (1055911110036, "CorpSAG3", False), (1055911110036, "CorporationGoalDeliveries", True)])

    def test_refresh_without_a_token_fails_cleanly(self):
        with mock.patch.object(hangar, "token", return_value=None):
            with self.assertRaises(RuntimeError):
                hangar.refresh()


class ScheduleTests(TestCase):
    def test_schedule_names_the_next_read_that_sees_fresh_data(self):
        cache.delete(hangar.EXPIRES_KEY)
        now = dt.datetime(2026, 10, 24, 4, 50, tzinfo=dt.timezone.utc)
        with mock.patch.object(hangar.app_settings, "SHIPYARD_HANGAR_BEAT_MINUTE", 35):
            s = hangar.schedule(now=now, read_at=now - dt.timedelta(minutes=19))
            self.assertEqual(s["next_run"], dt.datetime(2026, 10, 24, 5, 35, tzinfo=dt.timezone.utc))
            self.assertEqual(s["effective"], s["next_run"])
            self.assertIsNone(s["fresh_at"])
            self.assertFalse(s["cached"])
            # EVE's copy renews at 06:10: the 05:35 read would show the same contents, the first useful read is 06:35
            cache.set(hangar.EXPIRES_KEY, dt.datetime(2026, 10, 24, 6, 10, tzinfo=dt.timezone.utc).isoformat(), 3600)
            s = hangar.schedule(now=now, read_at=now)
            self.assertEqual(s["effective"], dt.datetime(2026, 10, 24, 6, 35, tzinfo=dt.timezone.utc))
            self.assertTrue(s["cached"])
            # at :35 exactly the next run is an hour later
            s = hangar.schedule(now=dt.datetime(2026, 10, 24, 5, 35, tzinfo=dt.timezone.utc), read_at=now)
            self.assertEqual(s["next_run"], dt.datetime(2026, 10, 24, 6, 35, tzinfo=dt.timezone.utc))
        cache.delete(hangar.EXPIRES_KEY)

    def test_refresh_remembers_when_eve_renews_its_copy(self):
        cache.delete(hangar.EXPIRES_KEY)
        tok = mock.Mock(character_name="Catherine Frey")
        tok.valid_access_token.return_value = "x"
        with mock.patch.object(hangar, "token", return_value=tok), mock.patch.object(hangar.esi, "_authed", return_value=_page([])), \
             mock.patch.object(hangar.projects, "corp_id", return_value=CID), mock.patch("shipyard.services.projectbooks._names", return_value={}):
            hangar.refresh()
        self.assertEqual(cache.get(hangar.EXPIRES_KEY), "2026-10-24T05:31:00+00:00")
        cache.delete(hangar.EXPIRES_KEY)
