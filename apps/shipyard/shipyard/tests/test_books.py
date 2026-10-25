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
        for name in ("SHIPYARD_BOOKS_STOCK_WRITTEN_OFF",):  # the live settings write the real cap boosters off; the fixture keeps its own
            patch = mock.patch.object(books.app_settings, name, [])
            patch.start()
            self.addCleanup(patch.stop)
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

    def test_a_correction_transfer_to_the_director_division_counts_as_project_funding(self):
        """Projects funded from the Director division by mistake, then 679 M moved from the master wallet to division 7
        with "correction projects" in the reason (owner, 2026-10-25): the transfer is ISK put into projects, not money leaving."""
        p1 = CorpProject.objects.get(project_id="p1")
        ProjectSnapshot.objects.create(project=p1, taken_at=at(0.5), state="Active", reward_remaining=2387e6)
        before = books.compute()
        # the pool grew by 100 M with no master-wallet funding line (paid from division 7)
        p1.reward_remaining += 100e6
        p1.save()
        ProjectSnapshot.objects.create(project=p1, taken_at=at(12.5), state="Active", reward_remaining=2387e6 + 100e6)
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_701, division=1, date=at(12.6), ref_type="corporation_account_withdrawal", amount=-60e6,
                                        reason="correction projects", first_party_id=CORP, second_party_id=CORP)
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_702, division=1, date=at(12.7), ref_type="corporation_account_withdrawal", amount=-40e6,
                                        reason="correction projects", first_party_id=CORP, second_party_id=4444)  # to a character: the same
        d = books.compute()
        self.assertNotIn("Moved to the Director division", [m[0] for m in d["moves"] if abs(m[1] + 60e6) < 1])
        self.assertFalse([m for m in d["moves"] if m[0].startswith("Paid out: correction")])
        # a correction in (a project cancelled from the wrong wallet, the money came back): a refund of funding, not income
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_703, division=1, date=at(12.8), ref_type="player_donation", amount=25e6,
                                        reason="correction projects refund", first_party_id=4444, second_party_id=CORP)
        d2 = books.compute()
        self.assertFalse([m for m in d2["moves"] if m[0].startswith("Deposit: correction")])
        self.assertAlmostEqual(d2["result"], d["result"] + 25e6, places=0)  # the ISK is in the wallet; the pool did not move here
        self.assertLess(abs(d2["gap"]), 1.0)
        paid = next(m for m in d["moves"] if m[0].startswith("Project rewards paid"))
        self.assertAlmostEqual(paid[1], next(m for m in before["moves"] if m[0].startswith("Project rewards paid"))[1], places=0)
        self.assertAlmostEqual(d["result"], before["result"], places=0)
        self.assertLess(abs(d["gap"]), 1.0)

    def test_the_live_sheet_shows_the_wallet_as_eve_shows_it(self):
        """Owner's rule (2026-10-25): the wallet figures are EVE's live balances; the difference to the journal copy is one
        movement, so the sheet still reconciles; a past moment keeps the journal's balance."""
        journal = books.compute()
        live = {1: journal["wallet"] + 50e6, 2: 25e6 + 7e6, 7: 1e9}
        with mock.patch.object(books, "live_wallets", lambda: live):
            d = books.compute()
            past = books.compute(now=at(10))
        self.assertAlmostEqual(d["wallet"], journal["wallet"] + 50e6, places=0)
        self.assertAlmostEqual(d["other_divs"], 32e6, places=0)
        move = next(m for m in d["moves"] if m[0].startswith("Wallet as EVE shows it"))
        self.assertAlmostEqual(move[1], 50e6 + 7e6, places=0)
        self.assertAlmostEqual(d["result"], journal["result"] + 57e6, places=0)
        self.assertLess(abs(d["gap"]), 1.0)
        self.assertTrue(d["live_ahead"] is None or abs(d["live_ahead"]) < 1)
        self.assertAlmostEqual(past["wallet"], books.compute(now=at(10))["wallet"], places=0)
        rows = dict((r[0], r[1]) for g in d["asset_groups"] if g["key"] == "cash" for r in g["rows"])
        self.assertAlmostEqual(rows["Master wallet, division 1"], journal["wallet"] + 50e6, places=0)
        self.assertAlmostEqual(rows["Wallet division 2"], 32e6, places=0)

    def test_written_off_stock_leaves_the_books_in_one_movement(self):
        """Owner's rule (2026-10-25): the leftover Cap Boosters bought to convert are left out; their lots leave at cost."""
        before = books.compute()
        boosters = next(s for s in before["stock"] if s["type_id"] == 11289)
        self.assertGreater(boosters["value"], 0)
        with mock.patch.object(books.app_settings, "SHIPYARD_BOOKS_STOCK_WRITTEN_OFF", [11289]):
            d = books.compute()
        self.assertNotIn(11289, [s["type_id"] for s in d["stock"]])
        self.assertFalse([m for m in d["moves"] if "written off" in m[0].lower() and "stock" in m[0].lower()])
        import re as _re
        self.assertFalse([m for m in d["moves"] if _re.search(r"(?<!Navy )Cap Booster 800", m[0] + " " + m[2])])  # the input booster is never named (the Navy one is a product)
        move = next(m for m in d["moves"] if m[0] == "Bought on the market")
        self.assertAlmostEqual(move[1], -boosters["value"], places=0)  # their cost is simply spent
        self.assertAlmostEqual(d["result"], before["result"] - boosters["value"], places=0)
        self.assertLess(abs(d["gap"]), 1.0)

    def test_period_tiles_follow_the_period(self):
        """The four tiles under the donut count the period only: sales before the period's start stay out (0.34.3)."""
        whole = books.compute()
        self.assertAlmostEqual(whole["period_tiles"]["turnover"] - whole["period_tiles"]["net"], whole["period_tiles"]["cost"], places=2)
        later = books.compute(since=at(11.5), since_label="later")  # after the Navy Cap Booster sale of hour 12? no: after the Pyerite sale of hour 2
        self.assertLess(later["period_tiles"]["turnover"], whole["period_tiles"]["turnover"])
        self.assertAlmostEqual(later["period_tiles"]["turnover"] - later["period_tiles"]["net"], later["period_tiles"]["cost"], places=2)

    def test_structure_income_is_one_line_in_its_own_category(self):
        """Two transfers of structure income (one by the old 'raitaru' wording, one saying 'structure income') make one
        movement under the Structure income category (owner, 2026-10-23)."""
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_601, division=1, date=at(12.5), ref_type="player_donation", amount=59.9e6,
                                        reason="structure income", first_party_id=111, second_party_id=CORP)
        d = books.compute()
        lines = [m for m in d["moves"] if m[0].startswith("Structure income transferred")]
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0][1], 77e6 + 59.9e6)
        self.assertIn("77.0 M by", lines[0][2])
        self.assertIn("59.9 M by", lines[0][2])
        group = next(g for g in d["move_groups"] if g["key"] == "structure")
        self.assertEqual(group["label"], "Structure income")
        self.assertAlmostEqual(group["total"], 136.9e6)
        self.assertEqual(len(group["rows"]), 1)
        self.assertLess(abs(d["gap"]), 1.0)

    def test_the_period_menu_opens_a_period_on_the_fly(self):
        """Day, Week and Month on the Finance tab: section 2 counts from that moment, the opening is the position then,
        nothing is stored, and the sheet still reconciles."""
        p1 = CorpProject.objects.get(project_id="p1")
        ProjectSnapshot.objects.create(project=p1, taken_at=at(0.5), state="Active", reward_remaining=2387e6)
        ProjectSnapshot.objects.create(project=p1, taken_at=at(11), state="Active", reward_remaining=2350e6)
        whole = books.compute()
        past = books.compute(now=at(6) - dt.timedelta(microseconds=1))  # the opening holds what came before the start
        d = books.compute(since=at(6), since_label="the last day")
        self.assertEqual(d["since_label"], "the last day")
        self.assertAlmostEqual(d["opening_result"], past["result"], places=0)
        self.assertAlmostEqual(d["result"], whole["result"], places=0)
        self.assertAlmostEqual(d["period_result"], whole["result"] - past["result"], places=0)
        self.assertLess(abs(d["gap"]), 1.0)
        self.assertEqual(BooksBaseline.objects.count(), 1)  # nothing stored
        start, label = books.period_start("week", now=at(10))
        self.assertEqual(start, at(10) - dt.timedelta(days=7))
        self.assertIn("the last 7 days", label)
        self.assertEqual(books.period_start("report"), (None, None))
        self.assertEqual(books.period_start("nonsense"), (None, None))

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
        books.direct_sale(99_402, "300,000 Pyerite", note="half of the rest")
        d = books.compute()
        move = next(m for m in d["moves"] if m[0].startswith("Goods sold directly (300,000 Pyerite)"))
        self.assertIn("3.0 M of stock left the books", move[2])
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

    def test_registered_direct_sale_quotes_matches_by_code_and_shows_in_section_3(self):
        """Register a direct sale on the Finance tab (quote by the rule, a DS code), deposit with the code: the lots leave,
        section 3 carries one 'Direct sale of goods' line with the profit."""
        from ..models import MarketLocation, MaterialType, PriceSnapshot
        from ..services import directsales
        MaterialType.objects.get_or_create(type_id=35, defaults={"name": "Pyerite"})
        market = MarketLocation.objects.create(name="Jita", station_id=60003760, is_default=True)
        PriceSnapshot.objects.create(type_id=35, location=market, sell_min=16.0, buy_max=15.0)
        p2 = CorpProject.objects.get(project_id="p2")
        ProjectContribution.objects.create(project=p2, taken_at=at(11), character_id=4242, character_name="Miner", contributed=4_000_000)
        p1 = CorpProject.objects.get(project_id="p1")
        p1.reward_remaining -= 10e6
        p1.save()
        owner = get_user_model().objects.create_user("owner", password="x")
        self.assertEqual(directsales.parse_lines("Pyerite\t400000\n373 Crystalline Isogen-10\nZero-Point Condensate x2388\n\nMexallon 10"),
                         [("Pyerite", 400000, "Pyerite\t400000"), ("Crystalline Isogen-10", 373, "373 Crystalline Isogen-10"),
                          ("Zero-Point Condensate", 2388, "Zero-Point Condensate x2388"), ("Mexallon", 10, "Mexallon 10")])
        q = directsales.quote("Pyerite\t400,000\nUnobtainium\t5", owner)
        self.assertEqual([(ln["name"], ln["qty"], ln["unit"], ln["line"], ln["cost"]) for ln in q["lines"]], [("Pyerite", 400000, 15.0, 6e6, 4e6)])
        self.assertAlmostEqual(q["profit"], 2e6)
        # the six valuations with their margin against the project cost, and the sanity flags (0.26.0)
        ln = q["lines"][0]
        self.assertEqual((ln["buy"], ln["sell"], ln["repro"], ln["flags"], ln["cost_unit"], ln["cost_lots"]), (15.0, 16.0, None, [], 10.0, 4e6))
        # units beyond the goods held are priced at the project buy price, so the profit covers every unit
        q2 = directsales.quote("Pyerite	50,000,000", owner)
        l2 = q2["lines"][0]
        self.assertTrue(l2["short"])
        self.assertLess(l2["held"], 50_000_000)
        self.assertAlmostEqual(l2["cost_unit"], l2["cost_lots"] / l2["held"], places=2)
        self.assertAlmostEqual(l2["cost"], l2["cost_lots"] + (50_000_000 - l2["held"]) * l2["cost_unit"], delta=50_000_000 * 0.005)
        self.assertAlmostEqual(l2["profit"], l2["line"] - l2["cost"], places=2)
        self.assertAlmostEqual(q2["cost"], l2["cost"], places=2)
        self.assertAlmostEqual(ln["pct"], 0.5)
        self.assertAlmostEqual(q["pct"], 0.5)
        self.assertEqual([round(v["total"]) for v in q["valuations"]], [6_000_000, 4_000_000, 6_000_000, 6_400_000, 6_000_000, 6_000_000])
        self.assertEqual([v["is_cost"] for v in q["valuations"]], [False, True, False, False, False, False])
        self.assertAlmostEqual(q["valuations"][3]["pct"], 0.6)
        self.assertEqual(q["flagged"], 0)
        self.assertEqual(directsales.flags(10.0, 15.0, 16.0, None), ["quote 33% under Jita buy"])
        self.assertEqual(directsales.flags(12.0, 12.0, 16.0, 30.0), ["Jita spread 25% (sell 16.00, buy 12.00)", "reprocessing value 1.88x Jita sell"])
        self.assertEqual(directsales.flags(15.0, 17.0, 16.0, None), ["Jita buy 17.00 above sell 16.00"])
        self.assertEqual(directsales.flags(15.0, None, None, None), ["no Jita buy order", "no Jita sell order"])
        rows = [{"qty": 10, "unit": 9.0, "cost": 50.0, "is_ore": True, "repro": 9.0, "buy": 8.0, "sell": 8.5},
                {"qty": 2, "unit": 100.0, "cost": 150.0, "is_ore": False, "repro": None, "buy": 100.0, "sell": 110.0}]
        vals = directsales.valuations(rows)
        self.assertEqual([round(v["total"], 2) for v in vals], [290.0, 200.0, 280.0, 305.0, 290.0, 285.0])
        self.assertEqual([v["key"] for v in vals], ["rule", "cost", "buy", "sell", "repro", "capped"])
        # registering at another valuation reprices every line (0.34.1)
        q_buy = directsales.reprice(directsales.quote("Pyerite\t400,000", owner), "buy")
        self.assertEqual((q_buy["basis"], q_buy["lines"][0]["unit"], q_buy["total"]), ("buy", 15.0, 6e6))
        q_sell = directsales.reprice(directsales.quote("Pyerite\t400,000", owner), "sell")
        self.assertEqual((q_sell["lines"][0]["unit"], q_sell["total"]), (16.0, 6.4e6))
        self.assertIn("Jita sell", q_sell["lines"][0]["basis"])
        sale_sell = directsales.register("Pyerite\t400,000", owner, "sell")
        self.assertAlmostEqual(sale_sell.quote, 6.4e6)
        self.assertIn("priced at Jita sell", sale_sell.note)
        sale_sell.delete()
        self.assertAlmostEqual(vals[0]["pct"], 0.45)
        self.assertAlmostEqual(vals[5]["margin"], 85.0)
        self.assertEqual(len(q["problems"]), 1)
        sale = directsales.register("Pyerite\t400,000", owner)
        self.assertRegex(sale.code, r"^DS-[A-HJ-NP-Z2-9]{4}$")
        self.assertEqual([s.code for s in directsales.pending()], [sale.code])
        before = books.compute()
        self.assertNotIn("direct", [g["key"] for g in before["project_bb"]["months"][0]["groups"]])
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_501, division=1, date=at(13), ref_type="player_donation", amount=6e6,
                                        reason=f"{sale.code.lower()} buyer paid", first_party_id=111, second_party_id=CORP)
        d = books.compute()
        move = next(m for m in d["moves"] if m[0].startswith("Goods sold directly (400,000 Pyerite)"))
        self.assertAlmostEqual(move[1], 6e6)
        self.assertIn("4.0 M of stock left the books", move[2])
        self.assertLess(abs(d["gap"]), 1.0)
        sale.refresh_from_db()
        self.assertEqual((sale.entry_id, sale.matched_at), (99_501, at(13)))
        self.assertEqual(directsales.pending(), [])
        group = next(g for g in d["project_bb"]["months"][0]["groups"] if g["key"] == "direct")
        self.assertEqual(group["label"], "Direct sale of goods")
        self.assertAlmostEqual(group["revenue"], 6e6)
        self.assertAlmostEqual(group["cost"], 4e6)
        self.assertAlmostEqual(group["net"], 2e6)
        self.assertAlmostEqual(d["project_bb"]["realised"], before["project_bb"]["realised"] + 2e6, places=0)

    def test_after_a_stock_take_ore_is_held_as_ore(self):
        """Owner's rule (2026-10-23): ore delivered after the last stock take stays compressed ore in the books, at what
        the project paid; a quote prices it from its own deliveries, and what an earlier registration sold is gone."""
        from ..models import MaterialType, Ore
        from ..services import directsales, projectbooks
        for tid, name in ((62536, "Compressed Kernite"), (36, "Tritanium"), (37, "Pyerite")):
            MaterialType.objects.get_or_create(type_id=tid, defaults={"name": name})
        Ore.objects.create(type_id=62536, name="Compressed Kernite", group_id=450, kind="ore", family="Kernite", variant="base", portion_size=100, materials={"36": 60, "37": 120}, volume=0.19)
        owner = get_user_model().objects.create_user("owner", password="x")
        wo = directsales.write_off(owner, "nothing held")
        wo.matched_at = at(11.5)
        wo.save(update_fields=["matched_at"])
        p3 = CorpProject.objects.create(project_id="p3", corporation_id=CORP, name="kernite", state="Active", reward_per_contribution=165.0,
                                        reward_initial=30e6, reward_remaining=30e6 - 14_406 * 165.0,
                                        details={"configuration": [{"deliver_item": {"items": [{"type_id": 62536}]}}]})
        ProjectContribution.objects.create(project=p3, taken_at=at(12), character_id=4242, character_name="Miner", contributed=14_406)
        led = projectbooks.ledger(CORP)
        self.assertIn(62536, led["lots"])
        self.assertEqual([(lot[1], lot[2], lot[3]) for lot in led["lots"][62536]], [(14_406.0, 165.0, "ore")])
        self.assertNotIn(36, led["lots"])
        q = directsales.quote("Compressed Kernite\t14,406", owner)
        ln = q["lines"][0]
        self.assertEqual((ln["cost_unit"], ln["cost"], ln["cost_lots"], ln["short"]), (165.0, 14_406 * 165.0, 14_406 * 165.0, False))
        held = dict(books.compute()["held"])
        self.assertAlmostEqual(held["Compressed Kernite"], 14_406 * 165.0, places=0)
        self.assertNotIn("Tritanium", held)
        # a registration already sold 10,000 of them: the next quote has 4,406 left at the project price
        directsales.register("Compressed Kernite\t10,000", owner)
        q2 = directsales.quote("Compressed Kernite\t10,000", owner)
        l2 = q2["lines"][0]
        self.assertEqual((l2["held"], l2["short"], l2["cost_unit"]), (4_406.0, True, 165.0))
        self.assertAlmostEqual(l2["cost"], 10_000 * 165.0)

    def test_direct_sale_of_ore_before_the_stock_take_takes_its_minerals(self):
        """0.27.3: ore delivered before the stock take sits in the books as minerals, ore delivered after it as ore. A direct
        sale dated before the stock take must take the minerals even when a later delivery gave the ore a lot of its own;
        before the fix it took nothing and the stock take wrote the goods off, which overstated the sale's margin."""
        from ..models import MarketLocation, MaterialType, Ore, PriceSnapshot
        from ..services import directsales, projectbooks
        for tid, name in ((62536, "Compressed Kernite"), (36, "Tritanium"), (37, "Pyerite")):
            MaterialType.objects.get_or_create(type_id=tid, defaults={"name": name})
        Ore.objects.create(type_id=62536, name="Compressed Kernite", group_id=450, kind="ore", family="Kernite", variant="base", portion_size=100, materials={"36": 60, "37": 120}, volume=0.19)
        market = MarketLocation.objects.create(name="Jita", station_id=60003760, is_default=True)
        for tid, price in ((36, 5.0), (37, 10.0), (62536, 200.0)):
            PriceSnapshot.objects.create(type_id=tid, location=market, sell_min=price, buy_max=price)  # the split of an ore's cost over its minerals goes by value
        owner = get_user_model().objects.create_user("owner", password="x")
        p3 = CorpProject.objects.create(project_id="p3", corporation_id=CORP, name="kernite", state="Active", reward_per_contribution=165.0,
                                        reward_initial=30e6, reward_remaining=30e6 - 2 * 14_406 * 165.0,
                                        details={"configuration": [{"deliver_item": {"items": [{"type_id": 62536}]}}]})
        ProjectContribution.objects.create(project=p3, taken_at=at(10), character_id=4242, character_name="Miner", contributed=14_406)
        sale = directsales.register("Compressed Kernite	14,406", owner)
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_601, division=1, date=at(11), ref_type="player_donation", amount=3e6,
                                        reason=f"{sale.code} ore sold", first_party_id=111, second_party_id=CORP)
        wo = directsales.write_off(owner, "stock take")
        wo.matched_at = at(11.5)
        wo.save(update_fields=["matched_at"])
        ProjectContribution.objects.create(project=p3, taken_at=at(12), character_id=4242, character_name="Miner", contributed=2 * 14_406)  # cumulative, as EVE reports it
        led = projectbooks.ledger(CORP)
        self.assertEqual([lot[3] for lot in led["lots"][62536]], ["ore"])  # the second delivery, held as ore
        self.assertIn(36, led["lots"])  # the first, as minerals
        d = books.compute()
        group = next(g for g in d["project_bb"]["months"][0]["groups"] if g["key"] == "direct")
        self.assertAlmostEqual(group["cost"], 14_406 * 165.0, places=0)  # the minerals of the first delivery, not nothing
        self.assertAlmostEqual(dict(d["held"])["Compressed Kernite"], 14_406 * 165.0, places=0)  # the second delivery untouched
        move = next(m for m in d["moves"] if m[0].startswith("Goods written off"))
        self.assertIn("0.0 M of project goods left the books", move[2])  # nothing was left for the stock take

    def test_goods_held_follow_the_hangar_once_read(self):
        """Owner's rule (2026-10-23): with a hangar read, the goods held are what is in the projects hangar, at the projects'
        prices; what the ledger expects but the hangar lacks shows as the hangar count against the ledger; the sheet reconciles."""
        from ..models import HangarItem, MaterialType
        MaterialType.objects.get_or_create(type_id=35, defaults={"name": "Pyerite"})
        p2 = CorpProject.objects.get(project_id="p2")
        ProjectContribution.objects.create(project=p2, taken_at=at(11), character_id=4242, character_name="Miner", contributed=4_000_000)
        p1 = CorpProject.objects.get(project_id="p1")
        p1.reward_remaining -= 10e6
        p1.save()
        before = books.compute()
        self.assertIsNone(before["hangar"]["read_at"])
        held_ledger = next(m for m in before["moves"] if m[0].startswith("Goods those rewards bought"))[1]
        self.assertAlmostEqual(held_ledger, 10e6, places=0)
        # the hangar holds 600,000 of the 1,000,000 Pyerite the ledger expects, plus Heavy Water (stock, ledger-style) and a stray item
        HangarItem.objects.create(corporation_id=CORP, type_id=35, name="Pyerite", quantity=600_000, location_id=1, location_flag="CorporationGoalDeliveries", read_at=at(12))
        HangarItem.objects.create(corporation_id=CORP, type_id=16272, name="Heavy Water", quantity=5, location_id=1, location_flag="CorporationGoalDeliveries", read_at=at(12))
        HangarItem.objects.create(corporation_id=CORP, type_id=99999, name="Stray", quantity=1, location_id=1, location_flag="CorporationGoalDeliveries", read_at=at(12))
        from ..services import hangar
        for name in ("SHIPYARD_BOOKS_HANGAR_LOCATIONS", "SHIPYARD_BOOKS_HANGAR_FLAGS"):  # the live settings pin the count to the real hangar
            patch = mock.patch.object(hangar.app_settings, name, [])
            patch.start()
            self.addCleanup(patch.stop)
        d = books.compute()
        self.assertEqual(d["hangar"]["types"], 1)
        self.assertEqual(d["hangar"]["extra"], ["Stray"])
        self.assertAlmostEqual(dict(d["held"])["Pyerite"], 6e6, places=0)
        self.assertAlmostEqual(d["held_total"], 6e6, places=0)
        diff = next(m for m in d["moves"] if m[0] == "Hangar count against the ledger")
        self.assertAlmostEqual(diff[1], -4e6, places=0)
        self.assertAlmostEqual(next(m for m in d["moves"] if m[0].startswith("Goods those rewards bought"))[1], 10e6, places=0)
        self.assertAlmostEqual(d["result"], before["result"] - 4e6, places=0)
        self.assertLess(abs(d["gap"]), 1.0)
        held_row = next(g for g in d["asset_groups"] if g["key"] == "held")
        self.assertAlmostEqual(held_row["total"], 6e6, places=0)
        # more in the hangar than the ledger: the excess at the newest lot's price
        HangarItem.objects.filter(type_id=35).update(quantity=1_200_000)
        d = books.compute()
        self.assertAlmostEqual(dict(d["held"])["Pyerite"], 12e6, places=0)
        self.assertAlmostEqual(next(m for m in d["moves"] if m[0] == "Hangar count against the ledger")[1], 2e6, places=0)
        self.assertLess(abs(d["gap"]), 1.0)

    def test_stock_take_writes_off_everything_held(self):
        """A stock take clears every project-goods lot at cost, moves no cash, and keeps the sheet reconciled."""
        from ..models import MaterialType
        from ..services import directsales
        MaterialType.objects.get_or_create(type_id=35, defaults={"name": "Pyerite"})
        p2 = CorpProject.objects.get(project_id="p2")
        ProjectContribution.objects.create(project=p2, taken_at=at(11), character_id=4242, character_name="Miner", contributed=4_000_000)
        p1 = CorpProject.objects.get(project_id="p1")
        p1.reward_remaining -= 10e6
        p1.save()
        before = books.compute()
        held_before = next(m for m in before["moves"] if m[0].startswith("Goods those rewards bought"))[1]
        self.assertAlmostEqual(held_before, 10e6, places=0)
        owner = get_user_model().objects.create_user("owner", password="x")
        wo = directsales.write_off(owner, "sold by direct trade earlier")
        self.assertTrue(wo.code.startswith("WO-"))
        self.assertNotIn(wo.code, [s.code for s in directsales.pending()])  # a stock take is not a sale waiting for its deposit
        self.assertAlmostEqual(wo.cost, 10e6, places=0)
        self.assertEqual([(ln["name"], ln["qty"]) for ln in wo.lines], [("Pyerite", 1_000_000.0)])
        d = books.compute()
        held_after = next(m for m in d["moves"] if m[0].startswith("Goods those rewards bought"))[1]
        self.assertAlmostEqual(held_after, 0.0, places=0)
        move = next(m for m in d["moves"] if m[0].startswith("Goods written off"))
        self.assertEqual(move[1], 0.0)
        self.assertIn("10.0 M of project goods left the books", move[2])
        self.assertAlmostEqual(d["result"], before["result"] - 10e6, places=0)
        self.assertLess(abs(d["gap"]), 1.0)
        self.assertNotIn("direct", [g["key"] for g in d["project_bb"]["months"][0]["groups"]])  # not a sale, not in section 3

    def test_a_line_can_be_ignored_in_part(self):
        """A settlement deposit that also brings real money: only the settling part leaves the books."""
        before = books.compute()
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_601, division=1, date=at(14), ref_type="manufacturing", amount=-54e6)
        dep = CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_602, division=1, date=at(15), ref_type="player_donation", amount=62e6,
                                              reason="correction manufacturing", first_party_id=111, second_party_id=CORP)
        books.ignore_entries([99_601], "accidental industry jobs")
        d = books.compute()
        self.assertAlmostEqual(d["result"], before["result"], places=0)  # the whole deposit leaves by its reason
        books.ignore_entries([dep.entry_id], "settles the jobs; 8 M stays as cash", amount=54e6)
        d = books.compute()
        self.assertAlmostEqual(d["result"], before["result"] + 8e6, places=0)
        self.assertAlmostEqual(d["ignored"]["net"], 0.0, places=0)
        self.assertEqual(d["ignored"]["count"], 2)
        self.assertIn("(54,000,000 of 62,000,000)", d["ignored"]["lines"][-1][3])
        self.assertLess(abs(d["gap"]), 1.0)
        self.assertTrue(any(m[0].startswith("Deposit: correction manufacturing") and abs(m[1] - 8e6) < 1 for m in d["moves"]))

    def test_lp_reasons_in_the_owners_spellings(self):
        for reason, units in (("50.000 LP", 50_000), ("15000 LP", 15_000), ("57k State protectorate LP", 57_000), ("11k State Protectorate LP", 11_000),
                              ("1.2M LP", 1_200_000), ("LP 16000", 16_000), ("correction LP withdrawl", None), ("raitaru tax income", None), ("", None)):
            self.assertEqual(books.lp_units_from(reason), units, reason)
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_701, division=1, date=at(16), ref_type="corporation_account_withdrawal", amount=-45.6e6,
                                        reason="57k State protectorate LP", first_party_id=CORP, second_party_id=222)
        bb = books.compute()["buyback"]
        self.assertEqual((bb["lp_units"], bb["lp_left"]), (50_000 + 57_000, 26_000 + 57_000))

    def test_corporation_lp_log_change_by_change(self):
        """The LP page: a purchase from the journal, conversions from the stock batches, a running balance."""
        events = books.compute()["lp_events"]
        self.assertEqual([(e["lp"], e["balance"]) for e in events], [(50_000, 50_000), (-24_000, 26_000)])
        self.assertIn("50,000 LP for 40.0 M (800 ISK per LP)", events[0]["what"])
        self.assertIn("Converted into 240 Navy Cap Booster 800", events[1]["what"])
        from allianceauth.tests.auth_utils import AuthUtils
        owner = get_user_model().objects.create_user("tony2", password="x")
        AuthUtils.add_main_character_2(owner, "tony2 main", 9003, corp_id=CORP, corp_name="OARMI", alliance_id=None, alliance_name="")
        owner.user_permissions.add(Permission.objects.get(codename="basic_access", content_type__app_label="shipyard"))
        owner.user_permissions.add(Permission.objects.get(codename="manage_shipyard", content_type__app_label="shipyard"))
        client = Client()
        client.force_login(owner)
        r = client.get(reverse("shipyard:finance_lp_log"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("26,000 LP", html)
        self.assertIn("Converted into 240 Navy Cap Booster 800", html)

    def test_lp_sold_directly(self):
        """0.28.1: a deposit whose reason names LP is a direct sale of LP (owner, 2026-10-23: "LP Purchase 69750"): the LP leave at
        average cost, the profit is one movement in the LP category and part of section 4, and the LP log shows the sale."""
        self.assertEqual(books.lp_units_from("LP Purchase 69750"), 69_750)
        before = books.compute()
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_701, division=1, date=at(13), ref_type="player_donation", amount=8.8e6,
                                        reason="LP Purchase 10000", first_party_id=111, second_party_id=CORP)
        d = books.compute()
        self.assertEqual((d["lp_units"], round(d["lp_cost"]), d["lp_sold"]), (16_000, 16_000 * 800, 10_000))
        move = next(m for m in d["moves"] if m[0].startswith("LP sold directly"))
        self.assertEqual(move[0], "LP sold directly: 10,000 LP")
        self.assertAlmostEqual(move[1], 0.8e6, places=0)
        self.assertIn("880 ISK per LP); 8.0 M at cost left the books", move[2])
        self.assertIn(move, next(g for g in d["move_groups"] if g["key"] == "lp")["rows"])
        self.assertNotIn("Deposit: LP Purchase 10000", [m[0] for m in d["moves"]])
        self.assertAlmostEqual(d["result"], before["result"] + 0.8e6, places=0)
        self.assertLess(abs(d["gap"]), 1.0)
        bb = d["buyback"]
        self.assertEqual((bb["lp_left"], bb["lp_sold"]), (16_000, 10_000))
        self.assertAlmostEqual(bb["realised"], before["buyback"]["realised"] + 0.8e6, places=0)
        month = bb["months"][0]
        self.assertEqual((month["lp_sold"], round(month["lp_sold_net"])), (10_000, 800_000))
        last = d["lp_events"][-1]
        self.assertEqual((last["lp"], last["balance"], last["kind"]), (-10_000, 16_000, "sold"))
        self.assertIn("Sold to", last["what"])
        self.assertEqual(next(g for g in d["asset_groups"] if g["key"] == "lp")["rows"][0][0], "16,000 LP not converted yet")

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

    def test_projects_funded_outside_the_master_wallet_are_flagged(self):
        """Owner's rule (2026-10-25): a project funded from any other wallet is always a mistake. The flag lists the funding
        lines since the baseline and stands while they exceed the corrections paid back from the master wallet."""
        CorpProject.objects.create(project_id="d7aaaaaa-1111", corporation_id=CORP, name="glist zeolites", state="Active", reward_initial=334.5e6, reward_remaining=314.1e6)
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_801, division=7, date=at(20), ref_type="project_payouts", amount=-334.5e6,
                                        reason="goal_id=d7aaaaaa-1111-2222:goal_name=glist zeolites", first_party_id=CORP, second_party_id=1000413)
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_802, division=7, date=BASE - dt.timedelta(hours=1), ref_type="project_payouts", amount=-150e6,
                                        reason="goal_id=before00-0000:goal_name=before the baseline", first_party_id=CORP, second_party_id=1000413)
        om = books.compute()["outside_master"]
        self.assertEqual([(ln["project"], ln["division"], ln["amount"], ln["state"]) for ln in om["lines"]], [("glist zeolites", 7, 334.5e6, "Active")])
        self.assertAlmostEqual(om["owed"], 334.5e6, places=0)
        self.assertEqual(len(om["open"]), 1)
        CorpProject.objects.filter(project_id="d7aaaaaa-1111").update(state="Closed", reward_remaining=0)
        self.assertEqual((len(books.compute()["outside_master"]["lines"]), books.compute()["outside_master"]["open"]), (1, []))  # closed ones stay out of the box
        CorpProject.objects.filter(project_id="d7aaaaaa-1111").update(state="Active", reward_remaining=314.1e6)
        # paid back to a character with the funding reason, and a plain "correction" transfer into the funding division: both count
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_803, division=1, date=at(20.1), ref_type="corporation_account_withdrawal", amount=-200e6,
                                        reason="correction projects", first_party_id=CORP, second_party_id=4444)
        CorpJournalEntry.objects.create(corporation_id=CORP, entry_id=99_804, division=1, date=at(20.2), ref_type="corporation_account_withdrawal", amount=-134.5e6,
                                        reason="correction", first_party_id=CORP, second_party_id=CORP)
        om = books.compute()["outside_master"]
        self.assertAlmostEqual(om["corrected"], 334.5e6, places=0)
        self.assertEqual(om["owed"], 0.0)
        self.assertEqual(books.compute(now=at(21))["outside_master"]["lines"], [])  # a past moment does not flag
        # the hourly flag tells the finance users once per line
        owner = get_user_model().objects.create_user("tony_flag", password="x")
        owner.user_permissions.add(Permission.objects.get(codename="manage_shipyard", content_type__app_label="shipyard"))
        told = []
        with mock.patch.object(books, "_tell", lambda u, t, x: told.append((u.username, x))), mock.patch.object(books.timezone, "now", lambda: at(21)):
            from django.core.cache import cache
            cache.delete(books.OUTSIDE_MASTER_SEEN)
            self.assertEqual(books.flag_outside_master(), 1)
            self.assertEqual(books.flag_outside_master(), 0)
        self.assertTrue(told and "glist zeolites funded with 334.5 M from wallet division 7" in told[0][1])
        self.assertIn("still owed to the funding wallet 0.0 M", told[0][1])

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
        self.assertAlmostEqual(pb["margin"], (revenue - 30e6) / 30e6, places=6)  # the sale price against the cost, before fees
        at = pb["all_time"]
        self.assertEqual((round(at["paid"]), at["members"]), (30_000_000, 1))
        self.assertAlmostEqual(at["sold"], revenue, places=2)
        self.assertAlmostEqual(at["net"], revenue - 30e6 - 1.7e6, places=2)
        self.assertAlmostEqual(at["margin"], (revenue - 30e6) / 30e6, places=6)
        self.assertIsNotNone(at["first"])
        self.assertEqual(books.compute(since=BASE - dt.timedelta(days=7), since_label="Week")["period_fallback"], "Week")  # before the books begin: counts from the baseline, says so
        self.assertEqual(books.compute()["period_fallback"], "")
        bb = books.compute()["buyback"]
        self.assertAlmostEqual(bb["sold_value"], 10 * 211_100)
        self.assertGreater(bb["cost_sold"], 0)
        self.assertAlmostEqual(bb["margin"], (bb["sold_value"] - bb["cost_sold"]) / bb["cost_sold"], places=6)

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
        self.assertIn("balance sheet", html)
        self.assertIn("Download PDF", html)
        self.assertNotIn("Not explained", html)

    def test_period_tiles_tie(self):
        """The period's four figures (0.34.0): cost is what the turnover lost on the way to the net income."""
        pt = books.compute()["period_tiles"]
        self.assertEqual(set(pt), {"turnover", "cost", "net", "rewards", "lp_units", "lp_isk"})
        self.assertEqual((pt["lp_units"], pt["lp_isk"]), (50_000, 40e6))  # the fixture's LP purchases inside the period (0.35.2)
        self.assertEqual(books.compute(since=at(11.5), since_label="later")["period_tiles"]["lp_units"], 0)
        self.assertAlmostEqual(pt["cost"], pt["turnover"] - pt["net"], places=3)

    @unittest.skipUnless(__import__("importlib").util.find_spec("reportlab"), "reportlab not installed")
    def test_pdf(self):
        from ..services import books_pdf
        pdf = books_pdf.render(books.compute())
        self.assertTrue(pdf.startswith(b"%PDF"))
