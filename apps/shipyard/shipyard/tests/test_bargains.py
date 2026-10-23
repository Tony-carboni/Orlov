"""Bargains (0.29.0): the year per type out of EVE Ref's daily archives, the flags, the page."""

import bz2
import datetime as dt
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import MarketHistoryDay, MarketTypeStat
from ..services import bargains

HEADER = "average,date,highest,lowest,order_count,volume,http_last_modified,region_id,type_id"
TODAY = dt.date(2026, 10, 23)


def archive(day, rows):
    """A day's CSV as EVE Ref ships it (several regions; only The Forge counts)."""
    lines = [HEADER]
    for tid, avg, low, high, vol in rows:
        lines.append(f"{avg},{day.isoformat()},{high},{low},{vol // 100 + 1},{vol},2026-10-22T11:07:13Z,10000002,{tid}")
        lines.append(f"{avg * 2},{day.isoformat()},{high * 2},{low * 2},3,{vol},2026-10-22T11:07:13Z,10000043,{tid}")  # Domain, ignored
    return bz2.compress("\n".join(lines).encode())


def store(day, rows):
    packed = bargains.pack(bargains._forge_rows(bz2.decompress(archive(day, rows)).decode()))
    MarketHistoryDay.objects.create(day=day, total=len(rows) * 2, rows=len(rows), data=packed)


@override_settings(SHIPYARD_STANDALONE_HOST="")
class BargainsTests(TestCase):
    def setUp(self):
        # Tritanium (34): flat at 5 for a year, one dip to 3 on day 200, today 4 on the market; Megacyte (40): rising
        for back in range(1, 366):
            day = TODAY - dt.timedelta(days=back)
            trit = (34, 5.0, 4.9, 5.1, 1_000_000_000) if back != 200 else (34, 3.0, 3.0, 3.2, 1_000_000_000)
            mega = (40, 1000.0 + back, 990.0 + back, 1010.0 + back, 100_000)
            store(day, [trit, mega])
        # a day older than the year: must not count
        store(TODAY - dt.timedelta(days=380), [(34, 1.0, 1.0, 1.0, 1), (40, 10.0, 10.0, 10.0, 1)])

    def test_the_year_per_type(self):
        self.assertEqual(bargains.compute_stats(), 2)
        t = MarketTypeStat.objects.get(type_id=34)
        self.assertEqual((t.low52, t.low52_date, t.high52, t.days365, t.as_of), (3.0, TODAY - dt.timedelta(days=200), 5.1, 365, TODAY - dt.timedelta(days=1)))
        self.assertAlmostEqual(t.avg90, 5.0, places=6)
        self.assertAlmostEqual(t.avg365, (364 * 5.0 + 3.0) / 365, places=6)
        self.assertAlmostEqual(t.vol30, 1_000_000_000.0)
        self.assertAlmostEqual(t.isk30, 5_000_000_000.0)
        m = MarketTypeStat.objects.get(type_id=40)
        self.assertEqual((m.low52, m.low52_date), (991.0, TODAY - dt.timedelta(days=1)))
        self.assertEqual(m.high52, 1375.0)
        # prices arrive: Tritanium at 4 is 20 % under its 90-day average but not at its year's low; Megacyte at 800 is both (its 90-day average is 1,045.5)
        with mock.patch.object(bargains.fuzzwork, "station_aggregates", return_value={
                34: {"sell_min": 4.0, "sell_percentile": 4.0, "sell_volume": 1e9, "sell_orders": 10, "buy_max": 3.9},
                40: {"sell_min": 800.0, "sell_percentile": 805.0, "sell_volume": 1e5, "sell_orders": 3, "buy_max": 790.0}}):
            r = bargains.refresh_prices()
        self.assertEqual(r["types"], 2)
        t.refresh_from_db()
        m.refresh_from_db()
        self.assertEqual((t.flag_low, t.flag_dip), (False, True))
        self.assertAlmostEqual(t.vs90, -0.2, places=6)
        self.assertAlmostEqual(t.pos52, (4.0 - 3.0) / (5.1 - 3.0), places=6)
        self.assertEqual((m.flag_low, m.flag_dip), (True, True))
        self.assertEqual([s.type_id for s in bargains.rows(flag="low")], [40])
        self.assertEqual([s.type_id for s in bargains.rows(flag="dip")], [40, 34])  # the deeper dip first
        self.assertEqual([s.type_id for s in bargains.rows(flag="any", min_isk=1e9)], [34])
        self.assertEqual(bargains.rows(flag="all", q="zzz"), [])

    def test_sync_history_fetches_new_and_completed_days_only(self):
        MarketHistoryDay.objects.all().delete()
        totals = {(TODAY - dt.timedelta(days=b)).isoformat(): 4 for b in range(1, 4)}
        totals[(TODAY - dt.timedelta(days=2)).isoformat()] = 6  # completed since
        MarketHistoryDay.objects.create(day=TODAY - dt.timedelta(days=1), total=4, rows=2, data=bargains.pack([]))
        MarketHistoryDay.objects.create(day=TODAY - dt.timedelta(days=2), total=4, rows=2, data=bargains.pack([]))
        MarketHistoryDay.objects.create(day=TODAY - dt.timedelta(days=500), total=4, rows=2, data=bargains.pack([]))  # beyond the window
        fetched = []

        def fake_fetch(day):
            fetched.append(day)
            return bargains._forge_rows(bz2.decompress(archive(day, [(34, 5.0, 4.9, 5.1, 10)])).decode())
        with mock.patch.object(bargains, "get_json", return_value=totals), mock.patch.object(bargains, "fetch_day", side_effect=fake_fetch), \
             mock.patch.object(bargains.time, "sleep"):
            r = bargains.sync_history(days=400, today=TODAY)
        self.assertEqual(sorted(fetched), [TODAY - dt.timedelta(days=3), TODAY - dt.timedelta(days=2)])
        self.assertEqual((r["downloaded"], r["skipped"], r["dropped"], r["days"]), (2, 1, 1, 3))
        self.assertEqual(MarketHistoryDay.objects.get(day=TODAY - dt.timedelta(days=2)).total, 6)
        self.assertEqual(list(bargains.unpack(MarketHistoryDay.objects.get(day=TODAY - dt.timedelta(days=3)).data)), [(34, 5.0, 4.9, 5.1, 10.0, 1)])

    def test_group_paths_and_names(self):
        groups = {"4": {"market_group_id": 4, "name": {"en": "Ships"}, "child_market_group_ids": [5]},
                  "5": {"market_group_id": 5, "name": {"en": "Frigates"}, "parent_group_id": 4, "child_market_group_ids": [6]},
                  "6": {"market_group_id": 6, "name": {"en": "Standard Frigates"}, "parent_group_id": 5, "type_ids": [587, 588]}}
        self.assertEqual(bargains._group_paths(groups)[587], (6, "Ships › Frigates › Standard Frigates", "Ships"))
        bargains.compute_stats()
        with mock.patch.object(bargains, "groups_map", return_value={34: (18, "Manufacture & Research › Materials › Minerals", "Manufacture & Research")}):
            self.assertEqual(bargains.fill_groups(), 1)
        self.assertEqual(MarketTypeStat.objects.get(type_id=34).top_group, "Manufacture & Research")
        resp = mock.Mock(status_code=200)
        resp.json.return_value = [{"id": 34, "name": "Tritanium", "category": "inventory_type"}, {"id": 40, "name": "Megacyte", "category": "inventory_type"}]
        with mock.patch.object(bargains, "session") as s, mock.patch.object(bargains.time, "sleep"):
            s.return_value.post.return_value = resp
            self.assertEqual(bargains.fill_names(), 2)
        self.assertEqual(MarketTypeStat.objects.get(type_id=40).name, "Megacyte")
        self.assertEqual(bargains.top_groups(), [("Manufacture & Research", 1)])

    @override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                                 "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_page(self):
        bargains.compute_stats()
        MarketTypeStat.objects.filter(type_id=34).update(name="Tritanium", sell_min=4.0, buy_max=3.9, group_path="Minerals", top_group="Manufacture & Research")
        bargains.apply_flags()
        from allianceauth.tests.auth_utils import AuthUtils
        user = AuthUtils.create_user("buyer")
        AuthUtils.add_main_character_2(user, "Buyer", 1001, corp_id=98843356, corp_name="OARMI", alliance_id=None, alliance_name="")
        user = get_user_model().objects.get(pk=user.pk)
        user.user_permissions.add(Permission.objects.get(codename="basic_access", content_type__app_label="shipyard"))
        user = get_user_model().objects.get(pk=user.pk)
        client = Client()
        client.force_login(user)
        r = client.get(reverse("shipyard:bargains") + "?flag=all&min=0")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Tritanium", html)
        self.assertIn("under 90 d", html)
        r = client.get(reverse("shipyard:bargains") + "?flag=low&min=0")
        self.assertNotIn("Tritanium", r.content.decode())
