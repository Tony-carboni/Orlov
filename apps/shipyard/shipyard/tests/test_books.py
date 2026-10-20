"""Finance tab: the balance sheet against the working budget, its reconciliation, the page and the PDF."""
import datetime as dt
import unittest
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import BooksBaseline, BookStock, CorpJournalEntry, CorpProject, CorpWalletTransaction, ProjectContribution
from ..services import books

CORP = 98843356
BASE = dt.datetime(2026, 10, 18, 7, 40, tzinfo=dt.timezone.utc)


def at(hours):
    return BASE + dt.timedelta(hours=hours)


@override_settings(SHIPYARD_STANDALONE_HOST="", SHIPYARD_PROJECTS_CORP_ID=CORP, SHIPYARD_BOOKS_STRUCTURE_TRANSFER=r"raitaru")
class BooksTests(TestCase):
    def setUp(self):
        for name, value in (("live_wallets", {}), ("live_orders", []), ("order_history", [])):
            patch = mock.patch.object(books, name, lambda value=value: value)
            patch.start()
            self.addCleanup(patch.stop)
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
        # a closed project that bought 3,000,000 Pyerite from a member before that Pyerite sold
        p2 = CorpProject.objects.create(project_id="p2", corporation_id=CORP, name="pyerite", state="Closed", reward_per_contribution=10.0,
                                        details={"configuration": [{"deliver_item": {"items": [{"type_id": 35}]}}]})
        ProjectContribution.objects.create(project=p2, taken_at=at(0.5), character_id=4242, character_name="Miner", contributed=3_000_000)
        # the LP chain: input boosters bought by a buy order that filled at once, 12 LP-store offers, booster sales
        j(10, "market_escrow", -8_813_000, tx=3)
        CorpWalletTransaction.objects.create(transaction_id=3, corporation_id=CORP, division=1, date=at(10), type_id=11289, quantity=1000, unit_price=8813, is_buy=True)
        BookStock.objects.create(name="Navy Cap Booster 800", type_id=32014, units=240, bought_at=at(11), lp_used=24_000, input_type_id=11289, input_units=240,
                                 isk_paid=24e6, isk_paid_by="outside", list_price=211_100)
        sale = j(12, "market_transaction", 10 * 211_100, tx=4)
        CorpWalletTransaction.objects.create(transaction_id=4, corporation_id=CORP, division=1, date=at(12), type_id=32014, quantity=10, unit_price=211_100)
        j(12, "transaction_tax", -10 * 211_100 * 0.0337, entry_id=sale + 1)
        j(11.5, "brokers_fee", -50_000, entry_id=99_001)

    def test_sheet_reconciles_and_names_every_movement(self):
        d = books.compute()
        self.assertAlmostEqual(d["explained"], d["result"], places=2)
        self.assertLess(abs(d["gap"]), 1.0)
        labels = {m[0]: m[1] for m in d["moves"]}
        self.assertAlmostEqual(labels["Heavy Water sold, profit over its cost"], 10_000 * (149.9 - 108), places=2)
        self.assertAlmostEqual(labels["Project goods sold on the market (gross)"], 52e6, places=2)
        self.assertAlmostEqual(labels["Escrow of corporation buy orders"], 149.5e6)
        self.assertAlmostEqual(labels["Structure income transferred to the corporation"], 77e6)
        self.assertAlmostEqual(labels["Moved to the Director division"], -10e6)
        self.assertAlmostEqual(labels["Paid out: Reprocessing buybacks"], -1.3e6)
        self.assertAlmostEqual(labels["LP bought"], 0.0)
        # rewards paid = baseline pool + new funding - pool now = 2387 + 66 - 2350
        self.assertAlmostEqual(labels["Project rewards paid to members"], -(2387e6 + 66e6 - 2350e6), places=2)
        self.assertEqual((d["buyback"]["lp_units"], d["lp_units"]), (50_000, 26_000))  # 24,000 went into the boosters
        hw = next(s for s in d["stock"] if s["name"] == "Heavy Water")
        self.assertAlmostEqual(hw["units"], 1_990_000)
        self.assertAlmostEqual(hw["value"], 1_990_000 * 108)
        booster_lp = 2397e6 + 1_499_000 + 50e6 - 1.7e6 + 149.5e6 + 77e6 - 40e6 - 66e6 - 10e6 - 25e6 - 1.3e6 + 2e6
        booster_lp += -8_813_000 + 10 * 211_100 - 10 * 211_100 * 0.0337 - 50_000
        self.assertAlmostEqual(d["wallet"], booster_lp, places=2)
        self.assertAlmostEqual(d["other_divs"], 25e6)  # the SRP division's side of the transfer is kept
        self.assertEqual(d["cut"], at(12))  # the last journal line

    def test_buyback_chain(self):
        listed = [{"type_id": 32014, "is_buy": False, "price": 211_100.0, "remain": 230, "total": 240, "escrow": 0.0, "location_id": 1, "division": 1, "issued": at(11.5)}]
        with mock.patch.object(books, "live_orders", lambda: [dict(o) for o in listed]), mock.patch.object(books, "order_history", lambda: []):
            d = books.compute()
        self.assertLess(abs(d["gap"]), 1.0)
        bb = d["buyback"]
        self.assertEqual((bb["lp_units"], bb["lp_used"], bb["lp_left"]), (50_000, 24_000, 26_000))
        self.assertAlmostEqual(bb["lp_avg"], 800.0)
        month = bb["months"][0]
        self.assertEqual((month["label"], month["lp_bought"], month["lp_converted"]), ("October 2026", 50_000, 24_000))
        conv = month["converted"][0]
        cost_each = (24_000 * 800 + 240 * 8813 + 24e6) / 240
        self.assertEqual((conv["name"], conv["units"]), ("Navy Cap Booster 800", 240))
        self.assertAlmostEqual(conv["unit_cost"], cost_each)
        sale = month["sales"][0]
        self.assertEqual(sale["sold"], 10)
        self.assertAlmostEqual(sale["tax"], -10 * 211_100 * 0.0337)
        self.assertAlmostEqual(sale["broker"], -50_000)
        self.assertAlmostEqual(sale["net"], 10 * 211_100 - 10 * cost_each - 10 * 211_100 * 0.0337 - 50_000)
        still = month["still"][0]
        self.assertEqual(still["units"], 230)
        self.assertAlmostEqual(still["expected"], 230 * 211_100 * (1 - 0.0337) - 230 * cost_each)
        self.assertAlmostEqual(month["output_value"], 10 * 211_100 + 230 * 211_100)
        # the input boosters not converted are ordinary stock
        left = next(x for x in d["stock"] if x["type_id"] == 11289)
        self.assertEqual(left["units"], 760)
        self.assertAlmostEqual(bb["outside"], 24e6)
        labels = {m[0]: m[1] for m in d["moves"]}
        self.assertAlmostEqual(labels["LP store: 240 Navy Cap Booster 800"], 24e6)  # the ISK from a character's own wallet
        self.assertAlmostEqual(labels["Bought on the market"], 0.0)
        self.assertAlmostEqual(d["lp_cost"], 26_000 * 800)
        # paid from a corporation wallet instead: the LP store payment and the redemption net to nothing
        BookStock.objects.filter(type_id=32014).update(isk_paid_by="corp")
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_002, division=1, date=at(10.9), ref_type="lp_store", amount=-24e6)
        with mock.patch.object(books, "live_orders", lambda: [dict(o) for o in listed]), mock.patch.object(books, "order_history", lambda: []):
            d = books.compute()
        self.assertLess(abs(d["gap"]), 1.0)
        labels = {m[0]: m[1] for m in d["moves"]}
        self.assertAlmostEqual(labels["LP store: 240 Navy Cap Booster 800"], 0.0)
        self.assertNotIn("Paid in the LP store, not entered as stock", labels)

    def test_project_buybacks(self):
        pb = books.compute()["project_bb"]
        month = pb["months"][0]
        self.assertEqual(month["label"], "October 2026")
        self.assertEqual([(r["name"], round(r["isk"])) for r in month["paid"]], [("Pyerite", 30_000_000)])
        self.assertEqual(month["members"], 1)
        row = month["sales"][0]
        self.assertEqual(row["name"], "Pyerite")
        revenue = 3_000_000 * 16.67  # what the transaction says the Pyerite sold for
        self.assertAlmostEqual(row["revenue"], revenue, places=2)
        self.assertAlmostEqual(row["cost"], 30e6)
        self.assertAlmostEqual(row["tax"], -1.7e6)
        self.assertAlmostEqual(row["net"], revenue - 30e6 - 1.7e6, places=2)
        self.assertAlmostEqual(month["realised"], revenue - 30e6 - 1.7e6, places=2)
        self.assertAlmostEqual(pb["paid_total"], 30e6)

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
