"""Finance tab: the balance sheet against the working budget, its reconciliation, the page and the PDF."""
import datetime as dt
import unittest
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import BookIgnoredEntry, BooksBaseline, BookStock, CorpJournalEntry, CorpProject, CorpWalletTransaction, ProjectContribution, ProjectSnapshot
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

    def test_a_new_period_opens_at_a_state_of_the_alliance_post(self):
        """A post dated after the budget baseline opens a period: section 2 then counts from there and adds
        up to the result minus the opening; stock, LP and goods keep counting from the budget baseline."""
        p1 = CorpProject.objects.get(project_id="p1")
        ProjectSnapshot.objects.create(project=p1, taken_at=at(0.5), state="Active", reward_remaining=2387e6)
        ProjectSnapshot.objects.create(project=p1, taken_at=at(11), state="Active", reward_remaining=2350e6)
        before = books.compute()
        posts = [(dt.date(2026, 10, 18), "State of the Alliance, October", "2026-10-18-state-of-the-alliance-october")]
        with mock.patch.object(books, "state_posts", lambda: posts):
            self.assertIsNone(books.check_posts())  # the post's date is before the budget baseline of 07:40: nothing opens
        posts = [(dt.date(2026, 10, 19), "State of the Alliance, November", "2026-10-19-state-of-the-alliance-november")]
        with mock.patch.object(books, "state_posts", lambda: posts):
            period = books.check_posts()
            self.assertIsNotNone(period)
            self.assertIsNone(books.check_posts())  # once only
        self.assertEqual(period.taken_at, dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc))
        self.assertIn("November", period.source)
        opening = books.compute(now=period.taken_at)
        self.assertAlmostEqual(period.opening_result, opening["result"], places=2)
        self.assertAlmostEqual(period.held, opening["held_total"], places=2)
        d = books.compute()
        self.assertLess(abs(d["gap"]), 1.0)
        self.assertEqual(d["period"].pk, period.pk)
        self.assertAlmostEqual(d["result"], before["result"], places=2)  # the position does not change with the period
        self.assertAlmostEqual(sum(m[1] for m in d["moves"]), d["result"] - period.opening_result, places=2)
        # every movement in the new period is dated after its start (19 Oct 00:00 = hour 16.3): the Heavy Water
        # profit of hour 1 and the LP store redemption of hour 11 belong to the earlier period
        labels = [m[0] for m in d["moves"]]
        self.assertNotIn("Heavy Water sold, profit over its cost", labels)
        self.assertNotIn("LP store: 240 Navy Cap Booster 800", labels)
        self.assertEqual(labels, ["Project rewards paid to members", "Goods those rewards bought, still held"])
        self.assertAlmostEqual(d["moves"][0][1], 0.0, places=2)  # the pool did not move after the period's opening snapshot
        # a sale inside the new period shows up, and the period keeps adding up
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_201, division=1, date=at(20), ref_type="market_transaction", amount=5 * 211_100,
                                        context_id=5, context_id_type="market_transaction_id")
        CorpWalletTransaction.objects.create(transaction_id=5, corporation_id=CORP, division=1, date=at(20), type_id=32014, quantity=5, unit_price=211_100)
        d = books.compute()
        self.assertLess(abs(d["gap"]), 1.0)
        self.assertIn("Navy Cap Booster 800 sold, profit over its cost", [m[0] for m in d["moves"]])
        self.assertIn("November", d["since_label"])
        # the stock position is unchanged
        self.assertAlmostEqual(next(s for s in d["stock"] if s["name"] == "Heavy Water")["units"], 1_990_000)

    def test_direct_sales_take_the_named_lots(self):
        """A deposit whose reason names the items sold takes them out of the goods held; a reason that does not
        is completed by an admin row (books.direct_sale)."""
        from ..models import MaterialType
        MaterialType.objects.get_or_create(type_id=35, defaults={"name": "Pyerite"})
        p2 = CorpProject.objects.get(project_id="p2")
        ProjectContribution.objects.create(project=p2, taken_at=at(11), character_id=4242, character_name="Miner", contributed=4_000_000)  # 1,000,000 more at 10, before the newest journal line (the sheet stops there)
        p1 = CorpProject.objects.get(project_id="p1")
        p1.reward_remaining -= 10e6  # the pool paid those 10 M
        p1.save()
        before = books.compute()
        held_before = next(m for m in before["moves"] if m[0].startswith("Goods those rewards bought"))[1]
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_401, division=1, date=at(13), ref_type="player_donation", amount=7e6,
                                        reason="direct sale 400,000 Pyerite", first_party_id=111, second_party_id=CORP)
        d = books.compute()
        move = next(m for m in d["moves"] if m[0].startswith("Goods sold directly"))
        self.assertEqual(move[0], "Goods sold directly (400,000 Pyerite)")
        self.assertAlmostEqual(move[1], 7e6)
        self.assertIn("4.0 M of stock left the books", move[2])
        held_after = next(m for m in d["moves"] if m[0].startswith("Goods those rewards bought"))[1]
        self.assertAlmostEqual(held_before - held_after, 4e6, places=0)
        self.assertAlmostEqual(d["result"], before["result"] + 7e6 - 4e6, places=0)
        self.assertLess(abs(d["gap"]), 1.0)
        # a deposit that names nothing: flagged on the page, then completed from the admin
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_402, division=1, date=at(14), ref_type="player_donation", amount=9e6,
                                        reason="Direct sale buyback goods", first_party_id=111, second_party_id=CORP)
        d = books.compute()
        move = next(m for m in d["moves"] if m[0].startswith("Goods sold directly (buyback"))
        self.assertIn("not matched: buyback goods", move[2])
        self.assertIn("0.0 M of stock left", move[2])
        books.direct_sale(99_402, "Pyerite", note="the rest of the Pyerite")
        d = books.compute()
        move = next(m for m in d["moves"] if m[0].startswith("Goods sold directly (600,000 Pyerite)"))
        self.assertIn("6.0 M of stock left the books", move[2])
        self.assertNotIn("not matched", move[2])
        self.assertLess(abs(d["gap"]), 1.0)
        self.assertEqual(books.parse_direct_sale_items("2,388 Zero-Point Condensate, 373 Crystalline Isogen-10; Pyerite x1.000 and Tritanium"),
                         [(2388, "Zero-Point Condensate"), (373, "Crystalline Isogen-10"), (1000, "Pyerite"), (None, "Tritanium")])
        self.assertEqual(books.parse_direct_sale_items("719k veld, 1.2M trit, 428,000 veld2, 2.5k zpc, 303 wg"),
                         [(719_000, "veld"), (1_200_000, "trit"), (428_000, "veld2"), (2_500, "zpc"), (303, "wg")])
        self.assertEqual(books.DIRECT_SALE.search("ds 2,388 zpc, 373 ci10").group(1), "2,388 zpc, 373 ci10")
        self.assertEqual(books.DIRECT_SALE.search("Direct sale: 300 wg").group(1), "300 wg")
        self.assertIsNone(books.DIRECT_SALE.search("funds for the fleet"))
        # the short form takes the lots too: 200,000 Pyerite by its abbreviation
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_403, division=1, date=at(15), ref_type="player_donation", amount=3e6,
                                        reason="ds 200k pye", first_party_id=111, second_party_id=CORP)
        d = books.compute()
        move = next(m for m in d["moves"] if m[0].startswith("Goods sold directly (200,000 Pyerite)"))
        self.assertIn("2.0 M of stock left the books", move[2])
        self.assertLess(abs(d["gap"]), 1.0)

    def test_ignored_lines_leave_the_books(self):
        """An accidental sale and its tax, flagged by id, and the owner's settlement, matched by its reason, net out."""
        before = books.compute()
        sale = CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_301, division=1, date=at(14), ref_type="market_transaction", amount=147.8e6,
                                               context_id=9, context_id_type="market_transaction_id")
        CorpWalletTransaction.objects.create(transaction_id=9, corporation_id=CORP, division=1, date=at(14), type_id=49711, quantity=1, unit_price=147.8e6)
        tax = CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_302, division=1, date=at(14), ref_type="transaction_tax", amount=-4.98e6)
        d = books.compute()
        self.assertAlmostEqual(d["result"], before["result"] + 147.8e6 - 4.98e6, places=2)
        self.assertEqual(books.ignore_entries([sale.entry_id, tax.entry_id], "accidental corporation order: Drekavac"), 2)
        self.assertEqual(books.ignore_entries([sale.entry_id], "again"), 0)
        d = books.compute()
        self.assertAlmostEqual(d["result"], before["result"], places=2)
        self.assertLess(abs(d["gap"]), 1.0)
        self.assertEqual(d["ignored"]["count"], 2)
        self.assertAlmostEqual(d["ignored"]["net"], 147.8e6 - 4.98e6, places=2)
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_303, division=1, date=at(15), ref_type="corporation_account_withdrawal", amount=-142.82e6,
                                        reason="accidental orders settlement", first_party_id=CORP, second_party_id=4444)
        d = books.compute()
        self.assertEqual(d["ignored"]["count"], 3)
        self.assertAlmostEqual(d["result"], before["result"], places=2)
        self.assertAlmostEqual(d["ignored"]["net"], 0.0, places=2)
        self.assertLess(abs(d["gap"]), 1.0)

    def test_categories_add_up(self):
        d = books.compute()
        self.assertAlmostEqual(sum(g["total"] for g in d["move_groups"]), d["result"], places=2)
        self.assertAlmostEqual(sum(g["total"] for g in d["asset_groups"]), d["assets"], places=2)
        self.assertEqual(sum(len(g["rows"]) for g in d["move_groups"]), len(d["moves"]))
        keys = [g["key"] for g in d["move_groups"]]
        self.assertEqual(keys, [k for k in keys if k != "gap"])  # nothing unexplained
        self.assertIn("lp", keys)
        self.assertIn("project_rewards", keys)
        self.assertEqual([g["key"] for g in d["asset_groups"]][:2], ["cash", "pool"])
        physical = next(g for g in d["asset_groups"] if g["key"] == "physical")
        self.assertEqual(len(physical["rows"]), 1)  # the 760 Cap Booster 800 left to convert
        listed = next(g for g in d["asset_groups"] if g["key"] == "listed")
        self.assertEqual(len(listed["rows"]), 2)  # Heavy Water and the listed Navy boosters

    def test_corrected_withdrawal_is_dropped(self):
        # a mistyped LP purchase paid back a minute later with "correction" in the reason: neither line counts
        j = lambda hours, ref, amount, reason="", entry_id=None: CorpJournalEntry.objects.create(  # noqa: E731
            corporation_id=CORP, entry_id=entry_id, division=1, date=at(hours), ref_type=ref, amount=amount, reason=reason,
            first_party_id=CORP if amount < 0 else 4444, second_party_id=4444 if amount < 0 else CORP)
        j(13, "corporation_account_withdrawal", -12e6, "LP 16000", entry_id=99_101)
        j(13.02, "player_donation", 12e6, "correction LP withdrawl", entry_id=99_102)
        j(13.03, "corporation_account_withdrawal", -12e6, "15000 LP", entry_id=99_103)
        d = books.compute()
        self.assertLess(abs(d["gap"]), 1.0)
        self.assertEqual(d["buyback"]["lp_units"], 65_000)  # 50,000 + 15,000, not 81,000
        self.assertAlmostEqual(d["buyback"]["lp_cost"], 52e6)
        self.assertFalse(any(m[0].startswith("Deposit: correction") for m in d["moves"]))

    def test_project_buybacks(self):
        pb = books.compute()["project_bb"]
        month = pb["months"][0]
        self.assertEqual(month["label"], "October 2026")
        self.assertEqual([g["key"] for g in month["groups"]], ["item"])  # Pyerite delivered as is: not an ore
        group = month["groups"][0]
        self.assertEqual((group["label"], group["members"], round(group["paid"])), ("Other items", 1, 30_000_000))
        row = group["rows"][0]
        self.assertEqual((row["name"], row["delivered"], round(row["paid"])), ("Pyerite", 3_000_000, 30_000_000))
        self.assertEqual(month["members"], 1)
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
