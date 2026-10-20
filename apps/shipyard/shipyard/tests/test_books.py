"""Finance tab: the balance sheet against the working budget, its reconciliation, the page and the PDF."""
import datetime as dt
import unittest
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import BooksBaseline, BookStock, CorpJournalEntry, CorpProject, CorpWalletTransaction
from ..services import books

CORP = 98843356
BASE = dt.datetime(2026, 10, 18, 7, 40, tzinfo=dt.timezone.utc)


def at(hours):
    return BASE + dt.timedelta(hours=hours)


@override_settings(SHIPYARD_STANDALONE_HOST="", SHIPYARD_PROJECTS_CORP_ID=CORP, SHIPYARD_BOOKS_STRUCTURE_TRANSFER=r"raitaru")
class BooksTests(TestCase):
    def setUp(self):
        wallets = mock.patch.object(books, "live_wallets", lambda: {})
        wallets.start()
        self.addCleanup(wallets.stop)
        patcher = mock.patch.object(books, "_names", lambda ids: {35: "Pyerite", 16272: "Heavy Water"})
        patcher.start()
        self.addCleanup(patcher.stop)
        BooksBaseline.objects.all().delete()  # the migration seeds the real baseline and batch
        BookStock.objects.all().delete()
        BooksBaseline.objects.create(taken_at=BASE, loan=5000e6, wallet=2397e6, pool=2387e6)
        BookStock.objects.create(name="Heavy Water", type_id=16272, units=2_000_000, unit_cost=108, bought_at=BASE - dt.timedelta(hours=2), list_price=149.9)
        CorpProject.objects.create(project_id="p1", corporation_id=CORP, name="bitumens", state="Active", reward_initial=2400e6, reward_remaining=2350e6)
        n = iter(range(1000, 2000))

        def j(hours, ref, amount, reason="", first=0, second=0, division=1, tx=0, entry_id=None):
            e = CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=entry_id or next(n), division=division, date=at(hours), ref_type=ref, amount=amount,
                                                first_party_id=first, second_party_id=second, reason=reason,
                                                context_id=tx, context_id_type="market_transaction_id" if tx else "")
            return e.entry_id
        # a Heavy Water sale and a project-goods sale, with their transactions
        j(1, "market_transaction", 10_000 * 149.9, tx=1)
        CorpWalletTransaction.objects.create(transaction_id=1, corporation_id=CORP, division=1, date=at(1), type_id=16272, quantity=10_000, unit_price=149.9, journal_ref_id=777)
        j(2, "market_transaction", 50e6, tx=2)
        CorpWalletTransaction.objects.create(transaction_id=2, corporation_id=CORP, division=1, date=at(2), type_id=35, quantity=3_000_000, unit_price=16.67, journal_ref_id=778)
        j(2, "transaction_tax", -1.7e6)
        j(3, "market_escrow", 149.5e6)
        j(4, "player_donation", 77e6, "raitaru tax income", first=111)
        j(5, "corporation_account_withdrawal", -40e6, "50.000 LP", first=CORP, second=222)
        j(6, "project_payouts", -66e6)  # a new project funded
        j(7, "corporation_account_withdrawal", -10e6, "", first=CORP, second=CORP)  # to the Director division
        j(7.5, "corporation_account_withdrawal", -25e6, "", first=CORP, second=CORP, entry_id=5555)  # to the SRP division: the same entry id in both journals
        j(7.5, "corporation_account_withdrawal", 25e6, "", first=CORP, second=CORP, division=2, entry_id=5555)
        j(8, "corporation_account_withdrawal", -1.3e6, "Reprocessing buybacks", first=CORP, second=333)
        j(9, "market_transaction", 2e6)  # a sale whose transaction EVE has not listed yet

    def test_sheet_reconciles_and_names_every_movement(self):
        d = books.compute()
        self.assertAlmostEqual(d["explained"], d["result"], places=2)
        self.assertLess(abs(d["gap"]), 1.0)
        labels = {m[0]: m[1] for m in d["moves"]}
        self.assertAlmostEqual(labels["Heavy Water sold, profit over its buy value"], 10_000 * (149.9 - 108), places=2)
        self.assertAlmostEqual(labels["Project goods sold on the market (gross)"], 52e6, places=2)
        self.assertAlmostEqual(labels["Escrow of corporation buy orders"], 149.5e6)
        self.assertAlmostEqual(labels["Structure income transferred to the corporation"], 77e6)
        self.assertAlmostEqual(labels["Moved to the Director division"], -10e6)
        self.assertAlmostEqual(labels["Paid out: Reprocessing buybacks"], -1.3e6)
        self.assertAlmostEqual(labels["LP bought"], 0.0)
        # rewards paid = baseline pool + new funding - pool now = 2387 + 66 - 2350
        self.assertAlmostEqual(labels["Project rewards paid to members"], -(2387e6 + 66e6 - 2350e6), places=2)
        self.assertEqual(d["lp_units"], 50_000)
        self.assertAlmostEqual(d["stock"][0]["units"], 1_990_000)
        self.assertAlmostEqual(d["stock_now"], 1_990_000 * 108)
        self.assertAlmostEqual(d["wallet"], 2397e6 + 1_499_000 + 50e6 - 1.7e6 + 149.5e6 + 77e6 - 40e6 - 66e6 - 10e6 - 25e6 - 1.3e6 + 2e6, places=2)
        self.assertAlmostEqual(d["other_divs"], 25e6)  # the SRP division's side of the transfer is kept
        self.assertEqual(d["cut"], at(9))

    def test_page_and_pdf_for_the_owner_only(self):
        owner = get_user_model().objects.create_user("tony", password="x")
        member = get_user_model().objects.create_user("member", password="x")
        from allianceauth.tests.auth_utils import AuthUtils
        for u, cid in ((owner, 9001), (member, 9002)):
            AuthUtils.add_main_character_2(u, f"{u.username} main", cid, corp_id=CORP, corp_name="OARMI", alliance_id=None, alliance_name="")
            u.user_permissions.add(Permission.objects.get(codename="basic_access", content_type__app_label="shipyard"))
        owner.user_permissions.add(Permission.objects.get(codename="manage_shipyard", content_type__app_label="shipyard"))
        client = Client()
        client.force_login(member)
        self.assertEqual(client.get(reverse("shipyard:finance")).status_code, 403)
        client.force_login(owner)
        r = client.get(reverse("shipyard:finance"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("simplified balance sheet", html)
        self.assertIn("Download PDF", html)
        self.assertNotIn("Not explained", html)

    @unittest.skipUnless(__import__("importlib").util.find_spec("reportlab"), "reportlab not installed")
    def test_pdf(self):
        from ..services import books_pdf
        pdf = books_pdf.render(books.compute())
        self.assertTrue(pdf.startswith(b"%PDF"))
