"""My business: wallet summary, sales and production pivots, the comparison and the chart data, on plain rows."""
import datetime as dt

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .. import constants
from ..models import CorpIndustryJob, Ship
from ..services import business


def _d(day):
    return dt.datetime(2026, 10, day, 12, 0, tzinfo=dt.timezone.utc)


class PureTests(SimpleTestCase):
    def setUp(self):
        self.sales = [
            {"date": _d(1), "type_id": 1, "name": "Rifter", "category": "Base", "hull": "Frigate", "quantity": 3, "unit_price": 1e6, "total": 3e6},
            {"date": _d(2), "type_id": 2, "name": "Vexor Navy Issue", "category": "Navy", "hull": "Cruiser", "quantity": 1, "unit_price": 1e8, "total": 1e8},
            {"date": _d(9), "type_id": 1, "name": "Rifter", "category": "Base", "hull": "Frigate", "quantity": 2, "unit_price": 1.1e6, "total": 2.2e6},
            {"date": _d(9), "type_id": 9, "name": "Nitrogen Fuel Block", "category": "Fuel", "hull": "Fuel block", "quantity": 400, "unit_price": 2e4, "total": 8e6},
        ]

    def test_sales_summary_groups_like_the_dashboard_and_keeps_fuel_apart(self):
        s = business.sales_summary(self.sales, "week")
        self.assertEqual((s["units"], s["lines"]), (6, 3))
        self.assertAlmostEqual(s["isk"], 105.2e6)
        self.assertEqual((s["fuel_units"], s["fuel_isk"]), (400, 8e6))
        self.assertEqual(s["by_category"]["columns"], ["2026-09-28 (wk 40)", "2026-10-05 (wk 41)"])
        self.assertEqual([r[0] for r in s["by_category"]["rows"]], ["Base", "Navy"])  # dashboard order, Base first
        self.assertEqual(s["by_category"]["rows"][0][2], 5)
        self.assertEqual([r[0] for r in s["by_hull"]["rows"]], ["Frigate", "Cruiser"])
        self.assertEqual(s["types"][0]["name"], "Rifter")
        self.assertEqual(s["types"][0]["units"], 5)
        self.assertAlmostEqual(s["types"][0]["average"], 5.2e6 / 5)
        self.assertEqual(s["fuel_types"][0]["units"], 400)
        self.assertEqual([r[0] for r in s["by_category_all"]["rows"]], ["Base", "Navy", "Fuel"])  # fuel last, as its own type
        self.assertEqual(s["fuel_by_name"]["rows"][0][0], "Nitrogen Fuel Block")
        self.assertEqual([r[0] for r in s["isk_by_category"]["rows"]], ["Base", "Navy", "Fuel"])  # ISK counts the fuel too

    def test_wallet_summary(self):
        rows = [
            {"date": _d(1), "ref_type": "market_transaction", "amount": 100.0},
            {"date": _d(1), "ref_type": "brokers_fee", "amount": -3.0},
            {"date": _d(8), "ref_type": "market_escrow", "amount": -50.0},
            {"date": _d(8), "ref_type": "transaction_tax", "amount": -2.0},
        ]
        w = business.wallet_summary(rows, "week")
        self.assertEqual((w["income"], w["expenses"], w["net"], w["count"]), (100.0, -55.0, 45.0, 4))
        self.assertEqual(w["types"][0], ("market_transaction", 1, 100.0))
        self.assertEqual([s["net"] for s in w["series"]], [97.0, -52.0])
        self.assertEqual(w["market"], {"sales": 100.0, "purchases": -50.0, "fees": -5.0})
        chart = business.wallet_chart(w)
        self.assertEqual(chart["datasets"][2]["type"], "line")
        self.assertEqual(chart["datasets"][0]["data"], [100.0, 0])

    def test_production_summary_and_comparison(self):
        now = _d(15)
        jobs = [
            {"job_id": 1, "date": _d(1), "end": _d(2), "status": "delivered", "type_id": 1, "name": "Rifter", "category": "Base", "hull": "Frigate", "runs": 10, "quantity": 10, "total": 1e6, "installer": "Catherine Frey"},
            {"job_id": 2, "date": _d(8), "end": _d(20), "status": "active", "type_id": 2, "name": "Vexor Navy Issue", "category": "Navy", "hull": "Cruiser", "runs": 2, "quantity": 2, "total": 4e6, "installer": "Catherine Frey"},
            {"job_id": 3, "date": _d(8), "end": _d(9), "status": "delivered", "type_id": 9, "name": "Nitrogen Fuel Block", "category": "Fuel", "hull": "Fuel block", "runs": 5, "quantity": 200, "total": 1e5, "installer": "Catherine Frey"},
        ]
        p = business.production_summary(jobs, "week", now=now)
        self.assertEqual((p["jobs"], p["units"], p["fuel_units"], p["active"]), (3, 12, 200, 1))
        self.assertAlmostEqual(p["cost"], 5.1e6)
        self.assertAlmostEqual(p["per_week"]["units"], 12 / 2.0)  # 14 days of jobs = 2 weeks
        self.assertEqual(p["status"], {"delivered": 2, "active": 1})
        c = business.compare(business.sales_summary(self.sales, "week"), p)
        self.assertEqual([(x["category"], x["produced"], x["sold"], x["difference"]) for x in c], [("Base", 10, 5, 5), ("Navy", 2, 1, 1), ("Fuel", 200, 400, -200)])
        f = business.fuel_table(business.sales_summary(self.sales, "week"), p)
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["name"], f[0]["sold"], f[0]["produced"], f[0]["jobs"]), ("Nitrogen Fuel Block", 400, 200, 1))
        self.assertAlmostEqual(f[0]["average"], 2e4)
        self.assertAlmostEqual(f[0]["cost_per_unit"], 1e5 / 200)
        chart = business.chart(p["by_category"])
        self.assertEqual(chart["labels"], ["2026-09-28 (wk 40)", "2026-10-05 (wk 41)"])
        self.assertEqual(chart["datasets"][0], {"label": "Base", "data": [10, 0]})


class ProductionRowsTests(TestCase):
    def setUp(self):
        Ship.objects.create(type_id=587, name="Rifter", group_id=25, hull_size="Frigate", category=constants.CAT_BASE, blueprint_type_id=1, units_per_run=1)
        Ship.objects.create(type_id=4051, name="Nitrogen Fuel Block", group_id=1136, hull_size="Fuel block", category=constants.CAT_FUEL, blueprint_type_id=2, units_per_run=40)
        cid = business.corp_id()
        now = timezone.now()
        CorpIndustryJob.objects.create(job_id=1, corporation_id=cid, installer_id=11, installer_name="Catherine Frey", activity_id=1, product_type_id=587, runs=5, status="delivered", start_date=now - dt.timedelta(days=3), end_date=now - dt.timedelta(days=2), cost=1e6)
        CorpIndustryJob.objects.create(job_id=2, corporation_id=cid, installer_id=22, installer_name="Someone Else", activity_id=1, product_type_id=4051, runs=3, status="active", start_date=now - dt.timedelta(days=1), end_date=now + dt.timedelta(days=1), cost=5e4)
        CorpIndustryJob.objects.create(job_id=3, corporation_id=cid, installer_id=11, installer_name="Catherine Frey", activity_id=8, product_type_id=587, runs=1, status="delivered", start_date=now - dt.timedelta(days=3), end_date=now - dt.timedelta(days=2), cost=0)  # invention: not production
        CorpIndustryJob.objects.create(job_id=4, corporation_id=cid, installer_id=11, installer_name="Catherine Frey", activity_id=1, product_type_id=99999, runs=1, status="delivered", start_date=now - dt.timedelta(days=3), end_date=now - dt.timedelta(days=2), cost=0)  # not in the catalog

    def test_rows_filter_by_installer_and_range_and_multiply_fuel_runs(self):
        rows = business.production_rows()
        self.assertEqual(sorted(r["job_id"] for r in rows), [1, 2])
        fuel = next(r for r in rows if r["job_id"] == 2)
        self.assertEqual((fuel["quantity"], fuel["category"], fuel["installer"]), (120, "Fuel", "Someone Else"))
        self.assertEqual([r["job_id"] for r in business.production_rows(installer_id=11)], [1])
        self.assertEqual([r["job_id"] for r in business.production_rows(since=timezone.now() - dt.timedelta(days=2))], [2])
