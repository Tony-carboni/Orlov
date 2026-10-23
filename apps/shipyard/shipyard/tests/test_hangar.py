"""The projects hangar (0.27.0): ESI rows aggregated, the read stored, the count narrowed by the settings."""
import datetime as dt
from unittest import mock

from django.test import TestCase, override_settings

from ..models import HangarItem
from ..services import hangar

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
        ]
        with mock.patch.object(hangar, "token", return_value=tok), mock.patch.object(hangar.esi, "_authed_pages", return_value=rows), \
             mock.patch.object(hangar.projects, "corp_id", return_value=CID), mock.patch("shipyard.services.projectbooks._names", return_value={62536: "Compressed Kernite"}):
            r = hangar.refresh()
        self.assertEqual((r["rows"], r["types"], r["character"]), (3, 3, "Catherine Frey"))
        self.assertEqual(HangarItem.objects.filter(corporation_id=CID).count(), 3)
        units, names, read_at = hangar.stock(CID)
        self.assertEqual(units, {62536: 14406, 48112: 600, 35: 5})
        self.assertEqual(names[62536], "Compressed Kernite")
        self.assertIsNotNone(read_at)
        with override_settings(SHIPYARD_BOOKS_HANGAR_LOCATIONS=[RAITARU], SHIPYARD_BOOKS_HANGAR_FLAGS=["CorpSAG2"]):
            with mock.patch.object(hangar.app_settings, "SHIPYARD_BOOKS_HANGAR_LOCATIONS", [RAITARU]), mock.patch.object(hangar.app_settings, "SHIPYARD_BOOKS_HANGAR_FLAGS", ["CorpSAG2"]):
                units, _, _ = hangar.stock(CID)
                self.assertEqual(units, {62536: 14406})
                divs = hangar.divisions(CID)
        self.assertEqual([(d["flag"], d["wanted"]) for d in divs], [("CorpSAG1", False), ("CorpDeliveries", False), ("CorpSAG2", True)])
        # a second read replaces everything
        with mock.patch.object(hangar, "token", return_value=tok), mock.patch.object(hangar.esi, "_authed_pages", return_value=rows[:1]), \
             mock.patch.object(hangar.projects, "corp_id", return_value=CID), mock.patch("shipyard.services.projectbooks._names", return_value={}):
            hangar.refresh()
        self.assertEqual(HangarItem.objects.filter(corporation_id=CID).count(), 1)

    def test_refresh_without_a_token_fails_cleanly(self):
        with mock.patch.object(hangar, "token", return_value=None):
            with self.assertRaises(RuntimeError):
                hangar.refresh()
