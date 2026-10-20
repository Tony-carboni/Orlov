"""The directors' balance sheet: the corporation's position against the owner's working budget.

Owner's rules (2026-10-18, docs/handoff.md): the owner lent Orlov Arms International a working budget
(5,000 M: the master wallet, the reward ISK in the active projects and the stock at buy value at the
baseline moment). That loan counts as nothing; the corporation's result is everything above or below
it. Wallet division 7 is the owner's characters' shared wallet and never corporation money.

Sources, all from our hourly copies: the corp's journal and market transactions (services/ledger.py,
divisions 1 to 6), the active projects' pool (CorpProject), the project goods still held (first in,
first out, services/projectbooks.ledger), stock batches entered in the admin (BookStock, plus market
buys of those types), the structure corp's income journal (services/wallet.py) and the fuel block
prices (PriceSnapshot). The sheet stops at the last journal line, so every source agrees.

Every journal line since the baseline lands in exactly one movement, so the movements always add up
to the result; a difference would show as "not explained" (and is a bug).
"""

import datetime as dt
import re
from collections import defaultdict, deque

from django.utils import timezone

from .. import app_settings
from ..models import BooksBaseline, BookStock, CorpJournalEntry, CorpProject, CorpWalletTransaction, MarketLocation, PriceSnapshot
from . import projectbooks, projects

M = 1e6
FEES = ("brokers_fee", "transaction_tax", "market_provider_tax")
LP_REASON = re.compile(r"([\d.,]+)\s*LP\b", re.I)
DIRECT_SALE = re.compile(r"direct\s+sale\s+(.+)", re.I)
FUEL_BLOCKS = {4051: "Nitrogen", 4246: "Hydrogen", 4247: "Helium", 4312: "Oxygen"}
DIRECTOR_DIVISION = 7


def baseline():
    return BooksBaseline.objects.order_by("-taken_at").first()


def _names(ids) -> dict:
    """Names for characters, corporations and types: our tables first, EVE for the rest."""
    from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

    from ..models import MaterialType
    ids = {int(i) for i in ids if i}
    out = dict(EveCharacter.objects.filter(character_id__in=ids).values_list("character_id", "character_name"))
    out.update(EveCorporationInfo.objects.filter(corporation_id__in=ids).values_list("corporation_id", "corporation_name"))
    out.update(MaterialType.objects.filter(type_id__in=ids).values_list("type_id", "name"))
    missing = [i for i in ids if i not in out]
    if missing:
        try:
            import requests
            r = requests.post("https://esi.evetech.net/latest/universe/names/", json=missing[:1000], timeout=20)
            if r.ok:
                out.update({x["id"]: x["name"] for x in r.json()})
        except Exception:  # noqa: BLE001
            pass
    return out


def _when(t):
    return f"{t.day} {t:%B} {t:%H:%M}"


def compute(now=None) -> dict:
    """The sheet as plain numbers and labels (the page and the PDF draw it). None when there is no baseline."""
    b = baseline()
    if b is None:
        return None
    cid = projects.corp_id()
    base = b.taken_at
    divisions = list(app_settings.SHIPYARD_BOOKS_DIVISIONS)
    journal = list(CorpJournalEntry.objects.filter(corporation_id=cid, date__gte=base, division__in=divisions).order_by("date", "entry_id"))
    cut = journal[-1].date if journal else base
    if now is not None:
        journal = [e for e in journal if e.date <= now]
        cut = journal[-1].date if journal else base
    txs = {t.journal_ref_id: t for t in CorpWalletTransaction.objects.filter(corporation_id=cid, date__gte=base, date__lte=cut)}
    batches_qs = list(BookStock.objects.all().order_by("bought_at", "id"))
    stock_types = {s.type_id: s.name for s in batches_qs}
    names = _names([e.first_party_id for e in journal] + [e.second_party_id for e in journal] + [t.type_id for t in txs.values()])

    # --- the journal, line by line --------------------------------------------------------------
    cash = defaultdict(float)  # division -> ISK moved since the baseline
    goods_sales = defaultdict(float)
    untyped_sales = 0.0
    stock_sales = []  # [t, type_id, qty, revenue]
    stock_buys = []  # [t, type_id, qty, unit_price] (market buys of a stock type)
    other_buys = defaultdict(float)
    fees = escrow = project_net = 0.0
    deposits, direct_sales, payouts, others = [], [], [], defaultdict(float)
    lp_units, lp_cost = 0, 0.0
    stock_paid = []  # withdrawals that paid for a stock batch: [batch id, amount]
    transfers_out = 0.0
    batch_cost_left = {s.id: s.units * s.unit_cost for s in batches_qs if s.bought_at > base}
    for e in journal:
        cash[e.division] += e.amount
        rt = e.ref_type
        if rt == "market_transaction":
            t = txs.get(e.entry_id)
            if e.amount >= 0:
                if t is None:
                    untyped_sales += e.amount
                elif t.type_id in stock_types:
                    stock_sales.append([t.date, t.type_id, t.quantity, e.amount])
                else:
                    goods_sales[names.get(t.type_id, f"type {t.type_id}")] += e.amount
            else:
                if t is not None and t.type_id in stock_types:
                    stock_buys.append([t.date, t.type_id, t.quantity, -e.amount / max(t.quantity, 1)])
                else:
                    other_buys[names.get(t.type_id, "items") if t else "items"] += e.amount
        elif rt in FEES:
            fees += e.amount
        elif rt == "market_escrow":
            escrow += e.amount
        elif rt == "project_payouts":
            project_net += e.amount
        elif rt == "player_donation" and e.amount > 0:
            m = DIRECT_SALE.search(e.reason or "")
            row = {"t": e.date, "who": names.get(e.first_party_id, str(e.first_party_id)), "reason": e.reason, "amount": e.amount}
            (direct_sales if m else deposits).append({**row, "item": m.group(1).strip() if m else ""})
        elif rt == "corporation_account_withdrawal":
            if e.first_party_id == cid and e.second_party_id == cid:
                # between wallet divisions: within 1-6 it nets to zero; to division 7 it leaves the books
                transfers_out += e.amount
                continue
            lp = LP_REASON.search(e.reason or "")
            if lp and e.amount < 0:
                lp_units += int(re.sub(r"[.,]", "", lp.group(1)))
                lp_cost += -e.amount
                continue
            paid_batch = next((bid for bid, left in batch_cost_left.items() if left and abs(-e.amount - left) <= max(1.0, 0.001 * left)), None)
            if paid_batch is not None and e.amount < 0:
                stock_paid.append([paid_batch, -e.amount])
                batch_cost_left[paid_batch] = 0
                continue
            payouts.append({"t": e.date, "to": names.get(e.second_party_id, str(e.second_party_id)), "reason": e.reason, "amount": e.amount})
        else:
            others[rt] += e.amount

    # --- stock: batches first in, first out ------------------------------------------------------
    lots = defaultdict(deque)
    stock_base = 0.0
    entries = [[s.bought_at, s.type_id, float(s.units), s.unit_cost, s.name, s.list_price, s.location_name] for s in batches_qs]
    entries += [[t, tid, float(q), p, stock_types[tid], None, ""] for t, tid, q, p in stock_buys]
    for row in sorted(entries, key=lambda r: r[0]):
        lots[row[1]].append(list(row))
    sold = defaultdict(lambda: [0.0, 0.0, 0.0])  # type -> [qty, revenue, cost]
    for t, tid, qty, revenue in sorted(stock_sales, key=lambda r: r[0]):
        need = float(qty)
        q = lots[tid]
        cost = 0.0
        while need > 1e-9 and q:
            take = min(need, q[0][2])
            cost += take * q[0][3]
            q[0][2] -= take
            need -= take
            if q[0][2] <= 1e-9:
                q.popleft()
        s = sold[tid]
        s[0] += qty
        s[1] += revenue
        s[2] += cost
    stock_lines = []
    stock_now = 0.0
    for tid, name in stock_types.items():
        units = sum(r[2] for r in lots[tid])
        value = sum(r[2] * r[3] for r in lots[tid])
        stock_now += value
        last = next((s for s in reversed(batches_qs) if s.type_id == tid), None)
        stock_lines.append({"name": name, "units": units, "value": value, "sold": sold[tid][0],
                            "unit_cost": (value / units) if units else (last.unit_cost if last else 0),
                            "list_price": last.list_price if last else None, "location": last.location_name if last else ""})
    for s in batches_qs:
        if s.bought_at <= base:
            stock_base += s.units * s.unit_cost
    bought_since = sum(s.units * s.unit_cost for s in batches_qs if s.bought_at > base) + sum(q * p for _, _, q, p in stock_buys)

    # --- project goods still held, split at the baseline -----------------------------------------
    led = projectbooks.ledger(cid, until=cut)
    prices, pnames = led["prices"], led["names"]
    direct_words = [d["item"].lower().split()[0] for d in direct_sales if d["item"]]
    held, held_value, older_cost, older_value = defaultdict(float), 0.0, 0.0, 0.0
    for tid, queue in led["lots"].items():
        name = pnames.get(tid, str(tid))
        sold_directly = any(name.lower().startswith(w[:6]) for w in direct_words)
        for t, qty, cost in queue:
            if t >= base:
                if sold_directly:
                    continue
                held[name] += qty * cost
                held_value += qty * prices.get(tid, 0.0)
            else:
                older_cost += qty * cost
                older_value += qty * prices.get(tid, 0.0)
    held_total = sum(held.values())

    # --- position --------------------------------------------------------------------------------
    pool = sum(p.reward_remaining for p in CorpProject.objects.filter(corporation_id=cid, missing=False, state="Active"))
    n_projects = CorpProject.objects.filter(corporation_id=cid, missing=False, state="Active").count()
    wallet = b.wallet + cash.get(1, 0.0)
    other_divs = sum(v for d, v in cash.items() if d != 1)
    assets = wallet + other_divs + pool + stock_now + held_total + lp_cost
    result = assets - b.loan
    paid_members = b.pool + (-project_net) - pool

    # --- movements, in the order of the sheet ------------------------------------------------------
    moves = []
    typed = sorted(goods_sales.items(), key=lambda kv: -kv[1])
    if typed or untyped_sales:
        note = ", ".join(f"{k} {v / M:.1f}" for k, v in typed if v >= 0.05 * M)
        if untyped_sales > 0.05 * M:
            note += (f"; " if note else "") + f"{untyped_sales / M:.1f} M whose item types EVE has not listed yet"
        moves.append(["Project goods sold on the market (gross)", sum(goods_sales.values()) + untyped_sales, note])
    for d in direct_sales:
        moves.append([f"Goods sold directly ({d['item']})", d["amount"], f"Deposited by {d['who']}, {_when(d['t'])}; the lot left the stock"])
    for tid, (qty, revenue, cost) in sold.items():
        if qty:
            moves.append([f"{stock_types[tid]} sold, profit over its buy value", revenue - cost,
                          f"{qty:,.0f} units for {revenue / M:.1f} M, less what they cost = {cost / M:.1f} M"])
    if escrow:
        moves.append(["Escrow of corporation buy orders", escrow, "Returned (+) or set aside (−) for buy orders; an order placed before the baseline was not part of the budget"])
    for d in deposits:
        rule = app_settings.SHIPYARD_BOOKS_STRUCTURE_TRANSFER
        label = "Structure income transferred to the corporation" if rule and re.search(rule, d["reason"] or "", re.I) else f"Deposit: {d['reason'] or 'no reason given'}"
        moves.append([label, d["amount"], f"{d['who']}, {_when(d['t'])}"])
    if fees:
        moves.append(["Broker fees and sales tax", fees, ""])
    for p in payouts:
        moves.append([f"Paid out: {p['reason'] or 'no reason given'}", p["amount"], f"To {p['to']}, {_when(p['t'])}"])
    for name, amount in other_buys.items():
        moves.append([f"Bought on the market: {name}", amount, "Not tracked as stock"])
    if transfers_out:
        moves.append(["Moved to the Director division", transfers_out, "Leaves the corporation's books (the owner's shared wallet)"])
    for rt, amount in sorted(others.items()):
        moves.append([f"Other: {rt.replace('_', ' ')}", amount, ""])
    moves.append(["Project rewards paid to members", -paid_members, "Fall of the active projects' pool, corrected for ISK put into new projects and refunds of closed ones"])
    moves.append(["Goods those rewards bought, still held", held_total, "At cost, as in section 1"])
    if bought_since:
        paid_in_books = sum(a for _, a in stock_paid) + sum(q * p for _, _, q, p in stock_buys)
        moves.append(["Stock bought", bought_since - paid_in_books,
                      f"{bought_since / M:.1f} M of stock since the baseline, now held at buy value"
                      + (f"; {(bought_since - paid_in_books) / M:.1f} M of it not paid from a corporation wallet" if abs(bought_since - paid_in_books) >= 1 else "")])
    if lp_cost:
        moves.append(["LP bought", 0.0, f"{lp_cost / M:.1f} M paid for {lp_units:,} LP, now held at cost"])
    explained = sum(m[1] for m in moves)
    gap = result - explained
    if abs(gap) >= 1.0:
        moves.append(["Not explained", gap, "The journal and the position differ: a missing journal page or a new kind of entry"])

    # --- outside the books -----------------------------------------------------------------------
    director = None
    last7 = CorpJournalEntry.objects.filter(corporation_id=cid, division=DIRECTOR_DIVISION).order_by("-date", "-entry_id").first()
    if last7:
        director = last7.balance
    structure_income = None
    rule = app_settings.SHIPYARD_BOOKS_STRUCTURE_TRANSFER
    if rule:
        last_transfer = next((d["t"] for d in reversed(deposits) if re.search(rule, d["reason"] or "", re.I)), None)
        if last_transfer:
            try:
                from . import wallet as structure_wallet
                rows = structure_wallet.without_excluded(list(structure_wallet.income_entries(since=last_transfer)), structure_wallet.excluded_payers())
                structure_income = sum(r.amount for r in rows)
            except Exception:  # noqa: BLE001
                structure_income = None

    # --- fuel --------------------------------------------------------------------------------------
    market = MarketLocation.objects.filter(is_active=True).order_by("-is_default", "name").first()
    fuel_prices = sorted((p.sell_min, FUEL_BLOCKS[p.type_id]) for p in PriceSnapshot.objects.filter(location=market, type_id__in=list(FUEL_BLOCKS)) if p.sell_min)
    fuel_price, fuel_name = fuel_prices[0] if fuel_prices else (0.0, "")
    fuel_rows = []
    paying = 0
    for f in app_settings.SHIPYARD_BOOKS_FUEL:
        bph = int(f.get("blocks_per_hour", 0))
        sponsored = bool(f.get("sponsored"))
        if not sponsored:
            paying += bph
        fuel_rows.append({"name": f["name"], "bph": bph, "sponsored": sponsored,
                          "day": 0.0 if sponsored else bph * 24 * fuel_price, "month": 0.0 if sponsored else bph * 24 * 30 * fuel_price})
    hours = max(0.0, (cut - base).total_seconds() / 3600)

    return {
        "cut": cut, "base": base, "loan": b.loan, "wallet": wallet, "other_divs": other_divs, "pool": pool, "n_projects": n_projects,
        "stock": stock_lines, "stock_now": stock_now, "stock_base": stock_base,
        "held": sorted(held.items(), key=lambda kv: -kv[1]), "held_total": held_total, "held_value": held_value,
        "lp_units": lp_units, "lp_cost": lp_cost, "assets": assets, "result": result,
        "moves": moves, "explained": explained, "gap": gap,
        "director": director, "older": (older_cost, older_value), "structure_income": structure_income,
        "fuel_price": fuel_price, "fuel_name": fuel_name, "fuel_rows": fuel_rows, "fuel_paying_bph": paying,
        "fuel_burned": round(hours * paying), "fuel_burned_isk": round(hours * paying) * fuel_price,
        "generated": timezone.now(), "market": market.name if market else "",
    }


def refresh() -> list[str]:
    """Read EVE now: the projects, the corp's journal and transactions, the structure corp's journal."""
    from . import ledger, wallet as structure_wallet
    out = []
    for label, fn in (("projects", projects.refresh), ("corporation journal", ledger.refresh), ("structure income", structure_wallet.refresh)):
        try:
            fn()
            out.append(f"{label}: read")
        except Exception as exc:  # noqa: BLE001
            out.append(f"{label}: {exc}")
    return out
