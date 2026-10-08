"""Blueprint prices from public contracts (EVE Ref snapshot)."""
import csv
import io
import json
import os
import tarfile
import tempfile
from datetime import timedelta

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from ..models import ContractPrice, Ship
from ..services import contracts
from ..services.contracts import Offer, cheapest_runs_average


def offers(*per_run_and_runs):
    return [Offer(contract_id=i, price=p * r, runs=r) for i, (p, r) in enumerate(per_run_and_runs, 1)]


class AverageTests(SimpleTestCase):
    def test_owners_example(self):
        # copies at 1, 2, 3, 3, 3 M with one run each → (1+2+3+3+3)/5
        avg, runs, used = cheapest_runs_average(offers((1e6, 1), (3e6, 1), (2e6, 1), (3e6, 1), (3e6, 1), (9e6, 1)), 5)
        self.assertAlmostEqual(avg, 2.4e6)
        self.assertEqual((runs, used), (5, 5))

    def test_multi_run_copies_count_per_run(self):
        # one 10-run copy at 1 M per run covers the five runs alone
        avg, runs, used = cheapest_runs_average(offers((2e6, 1), (1e6, 10)), 5)
        self.assertAlmostEqual(avg, 1e6)
        self.assertEqual((runs, used), (5, 1))
        # a 3-run copy at 1 M plus two single runs at 2 M → (3×1 + 2×2)/5
        avg, runs, used = cheapest_runs_average(offers((2e6, 1), (1e6, 3), (2e6, 1), (5e6, 1)), 5)
        self.assertAlmostEqual(avg, 1.4e6)
        self.assertEqual((runs, used), (5, 3))

    def test_fewer_runs_than_wanted(self):
        avg, runs, used = cheapest_runs_average(offers((4e6, 1), (2e6, 1)), 5)
        self.assertAlmostEqual(avg, 3e6)
        self.assertEqual((runs, used), (2, 2))
        self.assertEqual(cheapest_runs_average([], 5), (None, 0, 0))

    def test_outliers_are_ignored(self):
        # Vigilant on 2026-10-08: 31.9, 36.7, 36.8 M and one at 9 B
        avg, runs, used = cheapest_runs_average(offers((31.9e6, 1), (36.7e6, 1), (36.8e6, 1), (9e9, 1)), 5, outlier_factor=3.0)
        self.assertAlmostEqual(avg, (31.9e6 + 36.7e6 + 36.8e6) / 3)
        self.assertEqual((runs, used), (3, 3))
        # without the guard the 9 B listing drags the figure up
        avg, _, _ = cheapest_runs_average(offers((31.9e6, 1), (36.7e6, 1), (36.8e6, 1), (9e9, 1)), 5, outlier_factor=None)
        self.assertGreater(avg, 2e9)


def make_snapshot(contract_rows, item_rows, scrape_end="2026-10-08T08:31:04Z"):
    """A tiny EVE Ref-style archive in a temporary file; returns its path."""
    fd, path = tempfile.mkstemp(suffix=".tar.bz2")
    os.close(fd)

    def add(tar, name, text):
        data = text.encode("utf-8")
        info = tarfile.TarInfo(name)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))

    def csv_text(fields, rows):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({f: r.get(f, "") for f in fields})
        return buf.getvalue()

    cfields = ["contract_id", "type", "price", "region_id", "station_id", "date_expired", "title"]
    ifields = ["contract_id", "type_id", "quantity", "is_included", "is_blueprint_copy", "runs", "material_efficiency", "time_efficiency"]
    with tarfile.open(path, "w:bz2") as tar:
        add(tar, "meta.json", json.dumps({"datasource": "tranquility", "scrape_end": scrape_end}))
        add(tar, "contracts.csv", csv_text(cfields, contract_rows))
        add(tar, "contract_items.csv", csv_text(ifields, item_rows))
    return path


class SnapshotTests(TestCase):
    def setUp(self):
        self.vindi = Ship.objects.create(type_id=17740, name="Vindicator", group_id=27, hull_size="Battleship",
                                         category="Pirate", blueprint_type_id=17741)
        self.worm = Ship.objects.create(type_id=17930, name="Worm", group_id=25, hull_size="Frigate",
                                        category="Pirate", blueprint_type_id=17931)
        self.caracal = Ship.objects.create(type_id=621, name="Caracal", group_id=26, hull_size="Cruiser",
                                           category="Base", blueprint_type_id=688)
        c = lambda cid, price, kind="item_exchange", region=10000002, station=60003760: {  # noqa: E731
            "contract_id": cid, "type": kind, "price": price, "region_id": region, "station_id": station,
            "date_expired": "2026-10-20T00:00:00Z", "title": "x"}
        i = lambda cid, tid, runs, qty=1, included="true", bpc="true", me=0, te=0: {  # noqa: E731
            "contract_id": cid, "type_id": tid, "quantity": qty, "is_included": included, "is_blueprint_copy": bpc,
            "runs": runs, "material_efficiency": me, "time_efficiency": te}
        self.path = make_snapshot(
            [c(1, 15e6), c(2, 15e6), c(3, 15e6), c(4, 180e6), c(5, 180e6), c(6, 20e6), c(7, 1e6, kind="auction"),
             c(8, 50e6), c(9, 12e6, region=10000043), c(10, 100e6), c(11, 0), c(12, 1e6, station=60008494)],
            [i(1, 17741, 1), i(2, 17741, 1), i(3, 17741, 1), i(4, 17741, 10), i(5, 17741, 10, me=10, te=20),
             i(6, 17741, 1), i(7, 17741, 1),                       # 7: auction, skipped
             i(8, 17741, 1), i(8, 17740, 1, bpc="false"),          # 8: bundle with a hull, skipped
             i(9, 17741, 1),                                       # 9: other region, skipped
             i(10, 17741, 1, included="false"), i(10, 34, 1),      # 10: the copy is what the issuer wants, skipped
             i(11, 17741, 1),                                      # 11: no price, skipped
             i(12, 17741, 1),                                      # 12: Perimeter, not Jita 4-4, skipped
             ],
        )

    def tearDown(self):
        os.unlink(self.path)

    def test_parse_and_refresh(self):
        quotes, snapshot_at = contracts.parse_snapshot(self.path, [17741, 17931])
        self.assertEqual(snapshot_at.isoformat(), "2026-10-08T08:31:04+00:00")
        per_run = sorted(o.per_run for o in quotes[17741].offers)
        self.assertEqual(per_run, [15e6, 15e6, 15e6, 18e6, 18e6, 20e6])
        self.assertEqual(quotes[17931].offers, [])
        # with the station filter off, the Perimeter contract counts as well
        quotes_all, _ = contracts.parse_snapshot(self.path, [17741], stations=[])
        self.assertEqual(len(quotes_all[17741].offers), 7)
        with override_settings(SHIPYARD_CONTRACT_CATEGORIES=["Pirate"]):
            from .. import app_settings
            with mock_setting(app_settings, "SHIPYARD_CONTRACT_CATEGORIES", ["Pirate"]):
                result = contracts.refresh(self.path)
        self.assertEqual((result["ships"], result["priced"], result["offers"]), (2, 1, 6))
        row = ContractPrice.objects.get(ship=self.vindi)
        # cheapest five runs: 15, 15, 15 M (one run each) then two runs of the 18 M ten-run copy
        self.assertAlmostEqual(float(row.price_per_run), (15e6 * 3 + 18e6 * 2) / 5)
        self.assertAlmostEqual(float(row.lowest_per_run), 15e6)
        self.assertEqual((row.runs_used, row.offers_used, row.contracts, row.runs_available), (5, 4, 6, 24))
        self.assertEqual(row.offers[0]["per_run"], 15e6)
        self.assertFalse(ContractPrice.objects.filter(ship=self.worm).exists())
        self.assertFalse(ContractPrice.objects.filter(ship=self.caracal).exists())
        # fresh rows feed the board; stale ones do not
        self.assertIn(self.vindi.type_id, contracts.fresh_prices())
        ContractPrice.objects.filter(ship=self.vindi).update(snapshot_at=timezone.now() - timedelta(days=3))
        self.assertNotIn(self.vindi.type_id, contracts.fresh_prices())


class mock_setting:
    """Swap one module-level value for the duration of a block (app_settings reads at import)."""

    def __init__(self, module, name, value):
        self.module, self.name, self.value = module, name, value

    def __enter__(self):
        self.old = getattr(self.module, self.name)
        setattr(self.module, self.name, self.value)

    def __exit__(self, *exc):
        setattr(self.module, self.name, self.old)
