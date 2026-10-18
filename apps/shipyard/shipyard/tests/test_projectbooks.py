"""Corp projects history (0.14.0): payouts from contributions, the backlog estimate, funding, and FIFO matching of sales."""
import datetime as dt
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from ..models import (CorpProject, CorpWalletTransaction, MarketLocation, MaterialType, Ore, PriceSnapshot, ProjectContribution,
                      ProjectSnapshot, WalletJournalEntry)
from ..services import ledger, projectbooks, projects, reprocessing

NOW = timezone.now().replace(microsecond=0)
VELD = 62516  # Compressed Veldspar: 100 units -> 400 Tritanium
TRIT = 34
ZPC = 48112  # Zero-Point Condensate, sold as delivered


def project(pid, name, type_id, rate, created, state="Active", progress=0):
    cfg = [{"deliver_item": {"items": [{"type_id": type_id}]}}] if type_id else []
    return CorpProject.objects.create(project_id=pid, corporation_id=projects.corp_id(), name=name, state=state, kind="deliver_item",
                                      reward_initial=1e9, reward_remaining=5e8, reward_per_contribution=rate, progress_current=progress,
                                      progress_desired=10**9, created=created, details={"configuration": cfg})


class BooksTests(TestCase):
    def setUp(self):
        self.market = MarketLocation.objects.create(name="Jita", station_id=60003760, is_default=True)
        Ore.objects.create(type_id=VELD, name="Compressed Veldspar", group_id=1, group_name="Veldspar", kind="ore", family="Veldspar",
                           portion_size=100, volume=0.001, materials={str(TRIT): 400})
        MaterialType.objects.create(type_id=TRIT, name="Tritanium")
        MaterialType.objects.create(type_id=ZPC, name="Zero-Point Condensate")
        PriceSnapshot.objects.create(type_id=VELD, location=self.market, buy_max=12.0)
        PriceSnapshot.objects.create(type_id=TRIT, location=self.market, buy_max=4.0)
        PriceSnapshot.objects.create(type_id=ZPC, location=self.market, buy_max=36_000.0)
        first_read = NOW - dt.timedelta(days=4)
        # ore project: started 4 days before the first read; Alice had 1,000,000 units by then, 500,000 more later
        self.veld = project("v1", "compressed veldspar", VELD, 10.0, first_read - dt.timedelta(days=4), progress=1_500_000)
        ProjectSnapshot.objects.create(project=self.veld, taken_at=first_read, progress_current=1_000_000, reward_remaining=9.9e8)
        ProjectContribution.objects.create(project=self.veld, taken_at=first_read, character_id=1, character_name="Alice", contributed=1_000_000)
        ProjectContribution.objects.create(project=self.veld, taken_at=NOW - dt.timedelta(days=2), character_id=1, character_name="Alice", contributed=1_500_000)
        # ZPC project: started after the reads began; Bob delivered 100 units at 30,000
        self.zpc = project("z1", "zero-point", ZPC, 30_000.0, NOW - dt.timedelta(days=3), progress=100)
        ProjectSnapshot.objects.create(project=self.zpc, taken_at=NOW - dt.timedelta(days=3) + dt.timedelta(minutes=30), progress_current=100, reward_remaining=1)
        ProjectContribution.objects.create(project=self.zpc, taken_at=NOW - dt.timedelta(days=3) + dt.timedelta(minutes=30), character_id=2,
                                           character_name="Bob", contributed=100)
        # a project deleted before anyone delivered: no payout
        project("d1", "Zeolites", VELD, 1125.0, NOW - dt.timedelta(days=1), state="Deleted", progress=100_000)
        # the journal: 50 M into the ZPC project
        WalletJournalEntry.objects.create(entry_id=1, corporation_id=projects.corp_id(), division=1, date=NOW - dt.timedelta(days=3),
                                          ref_type="project_payouts", amount=-50e6)

    def test_payouts_with_the_backlog_spread_and_marked(self):
        ev = projectbooks.payout_events()
        self.assertAlmostEqual(sum(e["isk"] for e in ev), 15e6 + 3e6)
        est = [e for e in ev if e["est"]]
        self.assertEqual(len(est), 4)  # the 4 days between the start and the first read
        self.assertAlmostEqual(sum(e["isk"] for e in est), 10e6)
        self.assertTrue(all(e["t"] < NOW - dt.timedelta(days=4) for e in est))
        self.assertEqual(sum(1 for e in ev if not e["est"]), 2)  # Alice's later 500,000 and Bob's ZPC

    def test_deleted_project_without_deliveries_pays_nothing(self):
        d = CorpProject.objects.get(project_id="d1")
        self.assertEqual(d.paid_out, 0.0)
        self.assertNotIn("Zeolites", [r["project"].name for r in projects.payout_deltas()])

    def test_sales_matched_first_in_first_out(self):
        y = reprocessing.yield_for(Ore.objects.get(type_id=VELD))
        trit_made = 1_500_000 / 100 * 400 * y
        # the corp sells half the Tritanium at 4.5, 60 ZPC at 37,000, and some Pyerite the projects never bought
        CorpWalletTransaction.objects.create(transaction_id=10, corporation_id=projects.corp_id(), division=1, date=NOW - dt.timedelta(hours=5),
                                             type_id=TRIT, quantity=int(trit_made / 2), unit_price=4.5)
        CorpWalletTransaction.objects.create(transaction_id=11, corporation_id=projects.corp_id(), division=1, date=NOW - dt.timedelta(hours=4),
                                             type_id=ZPC, quantity=60, unit_price=37_000.0)
        CorpWalletTransaction.objects.create(transaction_id=12, corporation_id=projects.corp_id(), division=1, date=NOW - dt.timedelta(hours=3),
                                             type_id=35, quantity=1000, unit_price=17.0)
        b = projectbooks.books()
        by = {m[1]: m for m in b["matches"]}
        self.assertEqual(set(by), {"Tritanium", "Zero-Point Condensate"})
        self.assertAlmostEqual(by["Tritanium"][3], 15e6 / 2, delta=20)  # half the ore's cost went with half its minerals
        self.assertAlmostEqual(by["Zero-Point Condensate"][2], 60 * 37_000.0)
        self.assertAlmostEqual(by["Zero-Point Condensate"][3], 60 * 30_000.0)
        self.assertEqual(b["others"], [])  # Pyerite is outside what the projects bought: not counted at all
        self.assertAlmostEqual(b["stock_now"]["cost"], 15e6 / 2 + 40 * 30_000.0, delta=20)
        self.assertEqual(b["funding"][0][1], -50e6)
        # a payout row: kind, ISK, value as delivered and reprocessed
        row = next(r for r in b["payouts"] if r[2] == "zero-point")
        self.assertEqual((row[1], row[5], row[8]), ("item", 3e6, 100 * 36_000.0))

    def test_a_sale_before_any_delivery_is_other_stock(self):
        CorpWalletTransaction.objects.create(transaction_id=20, corporation_id=projects.corp_id(), division=1, date=NOW - dt.timedelta(days=30),
                                             type_id=ZPC, quantity=10, unit_price=35_000.0)
        b = projectbooks.books()
        self.assertEqual(b["matches"], [])
        self.assertEqual(b["others"][0][1:], ["Zero-Point Condensate", 350_000.0])


class LedgerTests(TestCase):
    def test_refresh_copies_journal_and_transactions_once(self):
        def fake(path, access_token, params=None):
            r = mock.Mock(headers={"X-Pages": "1"})
            if path.endswith("/journal/"):
                r.json.return_value = [{"id": 900 + int(path.split("/")[-3]), "date": "2026-10-18T07:00:00Z", "ref_type": "project_payouts", "amount": -1e6}] if "/wallets/1/" in path else []
            else:
                r.json.return_value = [{"transaction_id": 77, "date": "2026-10-18T08:00:00Z", "type_id": TRIT, "quantity": 5, "unit_price": 4.0, "is_buy": False}] if "/wallets/1/" in path else []
            return r
        tok = mock.Mock(valid_access_token=mock.Mock(return_value="x"))
        with mock.patch.object(ledger, "token", return_value=tok), mock.patch.object(ledger.esi, "_authed", side_effect=fake), \
             mock.patch.object(ledger, "polite_pause"):
            self.assertEqual(ledger.refresh(), {"journal": 1, "transactions": 1})
            self.assertEqual(ledger.refresh(), {"journal": 0, "transactions": 0})
        self.assertEqual(WalletJournalEntry.objects.get(entry_id=901).corporation_id, projects.corp_id())
        self.assertEqual(CorpWalletTransaction.objects.get(transaction_id=77).quantity, 5)
