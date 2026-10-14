"""Structure income: period keys, pivot, payers and totals from a small ledger."""
import datetime as dt

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from ..models import WalletJournalEntry
from ..services import wallet


class PeriodTests(SimpleTestCase):
    def test_keys(self):
        when = dt.datetime(2026, 10, 14, 11, 0, tzinfo=dt.timezone.utc)  # a Wednesday
        self.assertEqual(wallet.period_key(when, "day"), "2026-10-14")
        self.assertEqual(wallet.period_key(when, "week"), "2026-10-12 (wk 42)")
        self.assertEqual(wallet.period_key(when, "month"), "2026-10")
        self.assertEqual(wallet.period_key(when, "quarter"), "2026 Q4")


class LedgerTests(TestCase):
    def setUp(self):
        now = timezone.now()
        cid = wallet.corp_id()
        rows = [
            (1, now - dt.timedelta(days=1), "industry_job_tax", 1_000_000, 90001, "Alice", 500, "Corp A"),
            (2, now - dt.timedelta(days=2), "industry_job_tax", 2_000_000, 90002, "Bob", 600, "Corp B"),
            (3, now - dt.timedelta(days=40), "reprocessing_tax", 4_000_000, 90001, "Alice", 500, "Corp A"),
            (4, now - dt.timedelta(days=1), "player_donation", 50_000_000, 90003, "Carol", 700, "Corp C"),  # not income
            (5, now - dt.timedelta(days=1), "office_rental_fee", -300_000, cid, "GWON", 0, ""),            # an expense
        ]
        for eid, when, ref, amount, fp, fpn, corp, corpn in rows:
            WalletJournalEntry.objects.create(entry_id=eid, corporation_id=cid, division=1, date=when, ref_type=ref, amount=amount,
                                              first_party_id=fp, first_party_name=fpn, first_party_corp_id=corp, first_party_corp_name=corpn,
                                              second_party_id=cid, second_party_name="GWON")

    def test_income_pivot_payers_totals(self):
        entries = list(wallet.income_entries())
        self.assertEqual(sorted(e.entry_id for e in entries), [1, 2, 3])  # donation and expense left out
        t = wallet.totals(entries)
        self.assertAlmostEqual(t["all"], 7_000_000)
        self.assertAlmostEqual(t["d7"], 3_000_000)
        self.assertAlmostEqual(t["d90"], 7_000_000)
        self.assertEqual(t["count"], 3)
        p = wallet.pivot(entries, "quarter")
        self.assertEqual(sum(total for _, _, total in p["rows"]), 7_000_000)
        self.assertEqual({name for name, _, _ in p["rows"]}, {"industry_job_tax", "reprocessing_tax"})
        payers = wallet.payers(entries, "month")
        self.assertEqual([x["name"] for x in payers], ["Alice", "Bob"])
        alice = payers[0]
        self.assertAlmostEqual(alice["total"], 5_000_000)
        self.assertAlmostEqual(alice["recent"], 1_000_000)
        self.assertEqual(alice["corp"], "Corp A")
        self.assertEqual(alice["count"], 2)
        # a range cuts the old entry
        recent = list(wallet.income_entries(timezone.now() - dt.timedelta(days=30)))
        self.assertEqual(sorted(e.entry_id for e in recent), [1, 2])
