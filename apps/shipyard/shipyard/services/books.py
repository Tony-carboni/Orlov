"""The directors' balance sheet: the corporation's position against the owner's working budget.

Owner's rules (2026-10-18, docs/handoff.md): the owner lent Orlov Arms International a working budget
(5,000 M: the master wallet, the reward ISK in the active projects and the stock at buy value at the
baseline moment). That loan counts as nothing; the corporation's result is everything above or below
it. Wallet division 7 is the owner's characters' shared wallet and never corporation money.

Sources, all from our hourly copies: the corp's journal and market transactions (services/ledger.py,
divisions 1 to 6), the active projects' pool (CorpProject), the project goods still held (first in,
first out, services/projectbooks.ledger), stock batches entered in the admin (BookStock), the corp's
market buys, the structure corp's income journal (services/wallet.py), the fuel block prices
(PriceSnapshot) and the corp's open market orders (EVE, cached 5 minutes). The sheet stops at the last
journal line, so every source agrees.

Stock (0.18.0): everything the corp bought to sell is a lot at cost, used first in, first out:
- a BookStock batch bought by direct trade (Heavy Water), paid by a matching wallet withdrawal or from
  outside the corporation;
- every market buy of the corp (a buy order filling at once draws on escrow; a market journal line
  names its transaction in context_id);
- an LP store redemption (a BookStock batch with lp_used / input / isk_paid): the LP it used (at what
  the corp paid per LP), the input items it used (from their lots) and the ISK of the offer become the
  new items' cost. ISK paid from a character's own wallet is a contribution to the corporation.

Every journal line since the baseline lands in exactly one movement, so the movements always add up
to the result; a difference would show as "not explained" (and is a bug).
"""

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


def _is_conversion(s) -> bool:
    return bool(s.lp_used or s.input_units or s.isk_paid)


def _take(queue, need):
    """Use `need` units from a deque of [t, qty, unit_cost] lots, oldest first. Returns (cost, units taken)."""
    cost = taken = 0.0
    while need > 1e-9 and queue:
        take = min(need, queue[0][1])
        cost += take * queue[0][2]
        queue[0][1] -= take
        need -= take
        taken += take
        if queue[0][1] <= 1e-9:
            queue.popleft()
    return cost, taken


def compute(now=None) -> dict:
    """The sheet as plain numbers and labels (the page and the PDF draw it). None when there is no baseline."""
    b = baseline()
    if b is None:
        return None
    cid = projects.corp_id()
    base = b.taken_at
    divisions = list(app_settings.SHIPYARD_BOOKS_DIVISIONS)
    journal = list(CorpJournalEntry.objects.filter(corporation_id=cid, date__gte=base, division__in=divisions).order_by("date", "entry_id"))
    if now is not None:
        journal = [e for e in journal if e.date <= now]
    cut = journal[-1].date if journal else base
    # a market journal line names its transaction in context_id (the transaction's journal_ref_id points elsewhere)
    txs = {t.transaction_id: t for t in CorpWalletTransaction.objects.filter(corporation_id=cid, date__gte=base, date__lte=cut)}
    batches = [s for s in BookStock.objects.all().order_by("bought_at", "id") if s.bought_at <= cut]
    stock_types = {s.type_id for s in batches} | {s.input_type_id for s in batches if s.input_type_id}
    stock_types |= {t.type_id for t in txs.values() if t.is_buy}
    names = _names([e.first_party_id for e in journal] + [e.second_party_id for e in journal] + [t.type_id for t in txs.values()] + list(stock_types))
    names.update({s.type_id: s.name for s in batches})

    # --- the journal, line by line --------------------------------------------------------------
    cash = defaultdict(float)  # division -> ISK moved since the baseline
    goods_sales = defaultdict(float)
    untyped_sales = 0.0
    stock_sales = []  # [t, type_id, qty, revenue, journal entry id]
    tax_by_entry = {}  # transaction_tax lines by entry id: a sale's tax is the line next to it
    broker_lines = []  # [t, amount]
    lp_purchases = []  # [t, units, isk, to]
    goods_sale_entries = []  # [journal entry id, type_id] of project-goods sales, to find their sales tax
    market_buys = []  # [t, type_id, qty, cost]
    other_buys = 0.0
    fees = escrow = project_net = lp_store_paid = 0.0
    deposits, direct_sales, payouts, others = [], [], [], defaultdict(float)
    lp_units, lp_cost = 0, 0.0
    stock_paid = []  # withdrawals that paid for a stock batch: [batch id, amount]
    transfers_out = 0.0
    purchase_left = {s.id: s.units * (s.unit_cost or 0) for s in batches if s.bought_at > base and not _is_conversion(s)}
    for e in journal:
        cash[e.division] += e.amount
        rt = e.ref_type
        t = txs.get(e.context_id) if e.context_id_type == "market_transaction_id" else None
        if rt == "market_transaction":
            if e.amount >= 0:
                if t is None:
                    untyped_sales += e.amount
                elif t.type_id in stock_types:
                    stock_sales.append([t.date, t.type_id, t.quantity, e.amount, e.entry_id])
                else:
                    goods_sales[names.get(t.type_id, f"type {t.type_id}")] += e.amount
                    goods_sale_entries.append([e.entry_id, t.type_id])
            elif t is not None:
                market_buys.append([t.date, t.type_id, t.quantity, -e.amount])
            else:
                other_buys += e.amount
        elif rt == "market_escrow" and t is not None and t.is_buy and e.amount < 0:
            market_buys.append([t.date, t.type_id, t.quantity, -e.amount])  # a buy order that filled at once
        elif rt == "market_escrow":
            escrow += e.amount
        elif rt in FEES:
            fees += e.amount
            if rt == "transaction_tax":
                tax_by_entry[e.entry_id] = e.amount
            elif rt == "brokers_fee":
                broker_lines.append([e.date, e.amount])
        elif rt == "project_payouts":
            project_net += e.amount
        elif rt == "lp_store":
            lp_store_paid += e.amount
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
                lp_purchases.append([e.date, int(re.sub(r"[.,]", "", lp.group(1))), -e.amount, names.get(e.second_party_id, str(e.second_party_id))])
                continue
            paid = next((bid for bid, left in purchase_left.items() if left and abs(-e.amount - left) <= max(1.0, 0.001 * left)), None)
            if paid is not None and e.amount < 0:
                stock_paid.append([paid, -e.amount])
                purchase_left[paid] = 0
                continue
            payouts.append({"t": e.date, "to": names.get(e.second_party_id, str(e.second_party_id)), "reason": e.reason, "amount": e.amount})
        else:
            others[rt] += e.amount

    # --- stock: every lot at cost, first in, first out ---------------------------------------------
    lp_avg = (lp_cost / lp_units) if lp_units else 0.0
    lots = defaultdict(deque)
    stock_base = 0.0
    events = []  # (t, order, kind, payload): purchases and redemptions before the sales of the same moment
    for s in batches:
        events.append((s.bought_at, 1 if _is_conversion(s) else 0, "batch", s))
    for t, tid, qty, cost in market_buys:
        events.append((t, 0, "buy", (tid, qty, cost)))
    for t, tid, qty, revenue, entry_id in stock_sales:
        tax = tax_by_entry.get(entry_id + 1, tax_by_entry.get(entry_id - 1, 0.0))
        events.append((t, 2, "sale", (tid, qty, revenue, tax)))
    sold = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])  # type -> [qty, revenue, cost, sales tax]
    bought_units = defaultdict(lambda: [0.0, 0.0])  # type -> [units, cost] bought on the market
    used_units = defaultdict(lambda: [0.0, 0.0])  # type -> [units, cost] used in LP store offers
    lp_used = 0
    conversions = []
    for t, _, kind, p in sorted(events, key=lambda ev: (ev[0], ev[1])):
        if kind == "buy":
            tid, qty, cost = p
            lots[tid].append([t, float(qty), cost / qty if qty else 0.0])
            bought_units[tid][0] += qty
            bought_units[tid][1] += cost
        elif kind == "sale":
            tid, qty, revenue, tax = p
            cost, _ = _take(lots[tid], float(qty))
            s = sold[tid]
            s[0] += qty
            s[1] += revenue
            s[2] += cost
            s[3] += tax
        elif not _is_conversion(p):
            lots[p.type_id].append([t, float(p.units), p.unit_cost or 0.0])
            if t <= base:
                stock_base += p.units * (p.unit_cost or 0.0)
        else:
            lp_value = p.lp_used * lp_avg
            input_cost, input_taken = _take(lots[p.input_type_id], float(p.input_units)) if p.input_type_id and p.input_units else (0.0, 0.0)
            if p.input_type_id:
                used_units[p.input_type_id][0] += input_taken
                used_units[p.input_type_id][1] += input_cost
            total = lp_value + input_cost + p.isk_paid
            lots[p.type_id].append([t, float(p.units), total / p.units if p.units else 0.0])
            lp_used += p.lp_used
            conversions.append({"type_id": p.type_id, "t": t, "name": p.name, "units": p.units, "lp": p.lp_used, "lp_value": lp_value, "input": names.get(p.input_type_id, ""),
                                "input_units": input_taken, "input_cost": input_cost, "isk": p.isk_paid, "outside": p.isk_paid_by == "outside", "total": total})
    stock_lines = []
    stock_now = 0.0
    for tid in sorted(stock_types, key=lambda x: names.get(x, "")):
        units = sum(r[1] for r in lots[tid])
        value = sum(r[1] * r[2] for r in lots[tid])
        stock_now += value
        last = next((s for s in reversed(batches) if s.type_id == tid), None)
        if units > 1e-9 or sold[tid][0]:
            stock_lines.append({"name": names.get(tid, f"type {tid}"), "type_id": tid, "units": units, "value": value, "sold": sold[tid][0],
                                "unit_cost": (value / units) if units > 1e-9 else 0.0,
                                "list_price": last.list_price if last else None, "location": last.location_name if last else ""})
    bought_since = sum(s.units * (s.unit_cost or 0) for s in batches if s.bought_at > base and not _is_conversion(s))
    market_bought = sum(c for _, _, _, c in market_buys)
    lp_left = lp_cost - lp_used * lp_avg

    # --- project goods still held, split at the baseline -----------------------------------------
    led = projectbooks.ledger(cid, until=cut)
    prices, pnames = led["prices"], led["names"]
    direct_words = [d["item"].lower().split()[0] for d in direct_sales if d["item"]]
    held, held_value, older_cost, older_value = defaultdict(float), 0.0, 0.0, 0.0
    for tid, queue in led["lots"].items():
        if tid in stock_types:
            continue  # bought on the market or kept as stock: counted above
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

    # --- open orders (EVE now) ---------------------------------------------------------------------
    orders = live_orders()
    open_escrow = sum(o["escrow"] for o in orders if o["is_buy"] and o["issued"] <= cut)
    order_names = _names([o["type_id"] for o in orders if o["type_id"] not in names])
    for o in orders:
        o["name"] = names.get(o["type_id"]) or order_names.get(o["type_id"], f"type {o['type_id']}")
        lot = next((s for s in stock_lines if s["type_id"] == o["type_id"]), None)
        o["unit_cost"] = lot["unit_cost"] if lot else None
        o["value"] = o["remain"] * o["price"]

    # --- position --------------------------------------------------------------------------------
    pool = sum(p.reward_remaining for p in CorpProject.objects.filter(corporation_id=cid, missing=False, state="Active"))
    n_projects = CorpProject.objects.filter(corporation_id=cid, missing=False, state="Active").count()
    wallet = b.wallet + cash.get(1, 0.0)
    other_divs = sum(v for d, v in cash.items() if d != 1)
    assets = wallet + other_divs + pool + stock_now + held_total + lp_left + open_escrow
    result = assets - b.loan
    paid_members = b.pool + (-project_net) - pool

    # --- movements, in the order of the sheet ------------------------------------------------------
    moves = []
    typed = sorted(goods_sales.items(), key=lambda kv: -kv[1])
    if typed or untyped_sales:
        note = ", ".join(f"{k} {v / M:.1f}" for k, v in typed if v >= 0.05 * M)
        if untyped_sales > 0.05 * M:
            note += ("; " if note else "") + f"{untyped_sales / M:.1f} M whose item types EVE has not listed yet"
        moves.append(["Project goods sold on the market (gross)", sum(goods_sales.values()) + untyped_sales, note])
    for d in direct_sales:
        moves.append([f"Goods sold directly ({d['item']})", d["amount"], f"Deposited by {d['who']}, {_when(d['t'])}; the lot left the stock"])
    for tid, (qty, revenue, cost, _tax) in sold.items():
        if qty:
            moves.append([f"{names.get(tid, tid)} sold, profit over its cost", revenue - cost,
                          f"{qty:,.0f} units for {revenue / M:.1f} M, less what they cost = {cost / M:.1f} M"])
    if escrow:
        moves.append(["Escrow of corporation buy orders", escrow, "Set aside (−) for open buy orders or returned (+); an order placed before the baseline was not part of the budget"])
    if open_escrow:
        moves.append(["ISK still in open buy orders", open_escrow, "Corporation money waiting in buy orders (section 1)"])
    for d in deposits:
        rule = app_settings.SHIPYARD_BOOKS_STRUCTURE_TRANSFER
        label = "Structure income transferred to the corporation" if rule and re.search(rule, d["reason"] or "", re.I) else f"Deposit: {d['reason'] or 'no reason given'}"
        moves.append([label, d["amount"], f"{d['who']}, {_when(d['t'])}"])
    if fees:
        moves.append(["Broker fees and sales tax", fees, ""])
    for p in payouts:
        moves.append([f"Paid out: {p['reason'] or 'no reason given'}", p["amount"], f"To {p['to']}, {_when(p['t'])}"])
    if other_buys:
        moves.append(["Bought on the market, items not listed yet", other_buys, "EVE has not listed what was bought yet"])
    if transfers_out:
        moves.append(["Moved to the Director division", transfers_out, "Leaves the corporation's books (the owner's shared wallet)"])
    for rt, amount in sorted(others.items()):
        moves.append([f"Other: {rt.replace('_', ' ')}", amount, ""])
    moves.append(["Project rewards paid to members", -paid_members, "Fall of the active projects' pool, corrected for ISK put into new projects and refunds of closed ones"])
    moves.append(["Goods those rewards bought, still held", held_total, "At cost, as in section 1"])
    if market_bought:
        bought_names = sorted({names.get(tid, str(tid)) for _, tid, _, _ in market_buys})
        moves.append(["Bought on the market", 0.0, f"{market_bought / M:.1f} M paid for {', '.join(bought_names)}, held as stock at cost or used below"])
    corp_isk = sum(c["isk"] for c in conversions if not c["outside"])
    for c in conversions:
        value = c["isk"] if c["outside"] else 0.0  # corp-paid ISK nets against the LP store payment below
        inputs = f", {c['input_units']:,.0f} {c['input']} ({c['input_cost'] / M:.1f} M)" if c["input_units"] else ""
        who = "paid from outside the corporation's wallets: a contribution" if c["outside"] else "paid from a corporation wallet"
        moves.append([f"LP store: {c['units']:,} {c['name']}", value,
                      f"{c['lp']:,} LP ({c['lp_value'] / M:.1f} M at cost){inputs} and {c['isk'] / M:.1f} M ISK ({who}); now stock at {c['total'] / M:.1f} M"])
    if abs(lp_store_paid + corp_isk) >= 1:
        moves.append(["Paid in the LP store, not entered as stock", lp_store_paid + corp_isk,
                      "LP store payments from a corporation wallet without a matching redemption in the admin (stock batches)"])
    if bought_since:
        paid_in_books = sum(a for _, a in stock_paid)
        moves.append(["Stock bought", bought_since - paid_in_books,
                      f"{bought_since / M:.1f} M of stock since the baseline, now held at buy value"
                      + (f"; {(bought_since - paid_in_books) / M:.1f} M of it not paid from a corporation wallet" if abs(bought_since - paid_in_books) >= 1 else "")])
    if lp_cost:
        moves.append(["LP bought", 0.0, f"{lp_cost / M:.1f} M paid for {lp_units:,} LP, held at cost until used"])
    explained = sum(m[1] for m in moves)
    gap = result - explained
    goods_tax = defaultdict(float)
    for entry_id, tid in goods_sale_entries:
        goods_tax[tid] += tax_by_entry.get(entry_id + 1, tax_by_entry.get(entry_id - 1, 0.0))
    project_bb = _project_buybacks(cid, base, cut, led, goods_tax, _broker_by_type(broker_lines, orders), stock_types,
                                   held_total, held_value, older_cost, older_value, paid_members)
    buyback = _buyback(lp_purchases, lp_units, lp_cost, lp_avg, lp_used, lp_left, conversions, sold, lots, names,
                       bought_units, used_units, orders, broker_lines, batches)
    if abs(gap) >= 1.0:
        moves.append(["Not explained", gap, "The journal and the position differ: a missing journal page or a new kind of entry"])

    # --- outside the books -----------------------------------------------------------------------
    live = live_wallets()
    director = live.get(DIRECTOR_DIVISION)
    if director is None:
        last7 = CorpJournalEntry.objects.filter(corporation_id=cid, division=DIRECTOR_DIVISION).order_by("-date", "-entry_id").first()
        director = last7.balance if last7 else None
    live_books = sum(v for k, v in live.items() if k in divisions) if live else None
    books_now = wallet + other_divs
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
        "lp_units": lp_units - lp_used, "lp_cost": lp_left, "lp_bought": lp_units, "open_escrow": open_escrow,
        "assets": assets, "result": result, "moves": moves, "explained": explained, "gap": gap,
        "director": director, "older": (older_cost, older_value), "structure_income": structure_income,
        "live_books": live_books, "books_now": books_now, "live_ahead": (live_books - books_now) if live_books is not None else None,
        "orders": orders, "buyback": buyback, "project_bb": project_bb,
        "fuel_price": fuel_price, "fuel_name": fuel_name, "fuel_rows": fuel_rows, "fuel_paying_bph": paying,
        "fuel_burned": round(hours * paying), "fuel_burned_isk": round(hours * paying) * fuel_price,
        "generated": timezone.now(), "market": market.name if market else "",
    }


def _broker_by_type(broker_lines, orders) -> dict:
    """Broker fees of listings, by item type: a fee line at the moment an order was issued (within 90 s)
    belongs to the orders issued then, split by their value. Orders: open ones and EVE's order history."""
    out = defaultdict(float)
    listed = list(orders) + order_history()
    for t, amount in broker_lines:
        # the order issued (or last modified) nearest to the fee, within 90 seconds
        near = sorted((abs((o["issued"] - t).total_seconds()), i) for i, o in enumerate(listed) if abs((o["issued"] - t).total_seconds()) <= 90)
        if near:
            out[listed[near[0][1]]["type_id"]] += amount
    return out


def _buyback(lp_purchases, lp_units, lp_cost, lp_avg, lp_used, lp_left, conversions, sold, lots, names,
             bought_units, used_units, orders, broker_lines, batches) -> dict:
    """Buybacks and conversions (owner, 2026-10-20): the LP bought, the items bought to feed LP store
    offers, the redemptions, the sales of what came out, with their sales tax and broker fees."""
    brokers = _broker_by_type(broker_lines, orders)
    input_types = sorted({c_type for c_type in used_units} | {s.input_type_id for s in batches if s.input_type_id})
    output_types = []
    for c in conversions:
        if c["type_id"] not in output_types:
            output_types.append(c["type_id"])
    inputs = []
    for tid in input_types:
        left_units = sum(r[1] for r in lots[tid])
        left_cost = sum(r[1] * r[2] for r in lots[tid])
        inputs.append({"name": names.get(tid, f"type {tid}"), "bought": bought_units[tid][0], "bought_cost": bought_units[tid][1],
                       "used": used_units[tid][0], "used_cost": used_units[tid][1], "left": left_units, "left_cost": left_cost})
    products = []
    for tid in output_types:
        made = [c for c in conversions if c["type_id"] == tid]
        units = sum(c["units"] for c in made)
        cost = sum(c["total"] for c in made)
        qty, revenue, cost_sold, tax = sold[tid]
        broker = brokers.get(tid, 0.0)
        left_units = sum(r[1] for r in lots[tid])
        left_cost = sum(r[1] * r[2] for r in lots[tid])
        listed = [o for o in orders if o["type_id"] == tid and not o["is_buy"]]
        list_units = sum(o["remain"] for o in listed)
        list_value = sum(o["remain"] * o["price"] for o in listed)
        tax_rate = (-tax / revenue) if revenue else 0.0
        expected = list_value * (1 - tax_rate) - (left_cost * list_units / left_units if left_units else 0.0)
        products.append({"name": names.get(tid, f"type {tid}"), "made": units, "cost": cost, "unit_cost": cost / units if units else 0.0,
                         "lp": sum(c["lp"] for c in made), "lp_value": sum(c["lp_value"] for c in made),
                         "input_cost": sum(c["input_cost"] for c in made), "isk": sum(c["isk"] for c in made),
                         "outside": all(c["outside"] for c in made),
                         "sold": qty, "revenue": revenue, "cost_sold": cost_sold, "tax": tax, "broker": broker,
                         "net": revenue - cost_sold + tax + broker,
                         "left": left_units, "left_cost": left_cost, "list_units": list_units, "list_value": list_value,
                         "list_price": (list_value / list_units) if list_units else None, "expected": expected, "tax_rate": tax_rate})
    buying = [o for o in orders if o["is_buy"]]
    realised = sum(p["net"] for p in products)
    expected = sum(p["expected"] for p in products)
    outside = sum(p["isk"] for p in products if p["outside"])
    return {"lp_purchases": lp_purchases, "lp_units": lp_units, "lp_cost": lp_cost, "lp_avg": lp_avg, "lp_used": lp_used,
            "lp_left": lp_units - lp_used, "lp_left_value": lp_left, "inputs": inputs, "products": products, "buying": buying,
            "realised": realised, "expected": expected, "outside": outside,
            "stock_to_convert": sum(i["left_cost"] for i in inputs) + lp_left,
            "active": bool(lp_purchases or products or inputs)}


def _project_buybacks(cid, base, cut, led, goods_tax, brokers, stock_types, held_total, held_value, older_cost, older_value, paid_members) -> dict:
    """Project buybacks (owner, 2026-10-20): what the projects paid members since the baseline, by item,
    and what the corp sold of those items, at what the projects paid for them (first in, first out),
    with the sales tax and broker fees of those sales."""
    import datetime as dt

    pays = [e for e in projectbooks.payout_events(cid) if base <= e["t"] <= cut]
    type_names = _names({e["type_id"] for e in pays if e["type_id"]})
    paid = defaultdict(lambda: [0.0, 0.0, set()])  # item -> [units, isk, members]
    for e in pays:
        name = type_names.get(e["type_id"], e["project"]) if e["type_id"] else f"{e['project']} (no item)"
        row = paid[name]
        row[0] += e["units"]
        row[1] += e["isk"]
        row[2].add(e["member"])
    sold = defaultdict(lambda: [0.0, 0.0, 0.0])  # item -> [units, revenue, cost]
    bare = {int(m[1]) for m in led["matches"] + led["others"] if str(m[1]).isdigit()}
    fixed = _names(bare) if bare else {}
    led = dict(led, matches=[[w, fixed.get(int(n), n) if str(n).isdigit() else n, *rest] for w, n, *rest in led["matches"]],
               others=[[w, fixed.get(int(n), n) if str(n).isdigit() else n, *rest] for w, n, *rest in led["others"]])
    for when, name, revenue, cost, qty in led["matches"]:
        if dt.datetime.fromisoformat(when) >= base.replace(second=0, microsecond=0):
            row = sold[name]
            row[0] += qty
            row[1] += revenue
            row[2] += cost
    unmatched = defaultdict(float)
    for when, name, revenue in led["others"]:
        if dt.datetime.fromisoformat(when) >= base.replace(second=0, microsecond=0):
            unmatched[name] += revenue
    by_name = {}
    for tid, tax in goods_tax.items():
        by_name.setdefault(led["names"].get(tid) or _names([tid]).get(tid, str(tid)), [0.0, 0.0])[0] += tax
    for tid, fee in brokers.items():
        if tid in stock_types:
            continue
        by_name.setdefault(led["names"].get(tid) or _names([tid]).get(tid, str(tid)), [0.0, 0.0])[1] += fee
    rows = []
    for name in sorted(set(sold) | set(unmatched), key=lambda n: -(sold[n][1] + unmatched.get(n, 0.0))):
        units, revenue, cost = sold[name]
        tax, broker = by_name.get(name, [0.0, 0.0])
        rev_all = revenue + unmatched.get(name, 0.0)
        share = (revenue / rev_all) if rev_all else 0.0  # fees in proportion to the part that came from projects
        margin = revenue - cost + (tax + broker) * share
        rows.append({"name": name, "units": units, "revenue": revenue, "cost": cost, "tax": tax * share, "broker": broker * share,
                     "margin": margin, "pct": (margin / cost) if cost else None, "unmatched": unmatched.get(name, 0.0)})
    paid_rows = [{"name": n, "units": v[0], "isk": v[1], "members": len(v[2])} for n, v in sorted(paid.items(), key=lambda kv: -kv[1][1])]
    paid_total = sum(r["isk"] for r in paid_rows)
    revenue = sum(r["revenue"] for r in rows)
    cost = sum(r["cost"] for r in rows)
    fees = sum(r["tax"] + r["broker"] for r in rows)
    margin = sum(r["margin"] for r in rows)
    members = len({m for v in paid.values() for m in v[2]})
    return {"paid": paid_rows, "paid_total": paid_total, "paid_pool": paid_members, "members": members, "sold": rows,
            "revenue": revenue, "cost": cost, "fees": fees, "margin": margin, "pct": (margin / cost) if cost else None,
            "cash_net": revenue + fees - paid_total, "held": held_total, "held_value": held_value,
            "older": older_cost, "older_value": older_value, "unmatched": sum(unmatched.values()),
            "active": bool(paid_rows or rows)}


def order_history() -> list:
    """The corporation's closed orders of the last 90 days (cached 5 minutes), same shape as live_orders()."""
    import datetime as dt

    def read():
        try:
            from allianceauth.eveonline.models import EveCharacter
            from esi.models import Token

            from . import esi, ledger
            ids = list(EveCharacter.objects.filter(corporation_id=ledger.corp_id()).values_list("character_id", flat=True))
            tok = Token.objects.filter(character_id__in=ids).require_scopes(["esi-markets.read_corporation_orders.v1"]).require_valid().order_by("-created").first()
            if tok is None:
                return []
            rows = esi._authed(f"/corporations/{ledger.corp_id()}/orders/history/", tok.valid_access_token()).json() or []
            return [{"type_id": int(r["type_id"]), "is_buy": bool(r.get("is_buy_order")), "price": float(r["price"]),
                     "remain": int(r["volume_remain"]), "total": int(r["volume_total"]), "escrow": float(r.get("escrow") or 0),
                     "location_id": int(r["location_id"]), "division": int(r.get("wallet_division") or 1),
                     "issued": dt.datetime.fromisoformat(str(r["issued"]).replace("Z", "+00:00"))} for r in rows]
        except Exception:  # noqa: BLE001
            return []
    return [dict(o) for o in _cached_get("shipyard:books:history", read)]


def _cached_get(key, fn, seconds=300):
    from django.core.cache import cache
    cached = cache.get(key)
    if cached is not None:
        return cached
    value = fn()
    if value:
        cache.set(key, value, seconds)
    return value


def live_wallets() -> dict:
    """{division: balance} as EVE reports it now (cached 5 minutes); {} without a token or when EVE does not answer."""
    def read():
        try:
            from . import esi, ledger
            tok = ledger.token()
            if tok is None:
                return {}
            rows = esi._authed(f"/corporations/{ledger.corp_id()}/wallets/", tok.valid_access_token()).json() or []
            return {int(r["division"]): float(r["balance"]) for r in rows}
        except Exception:  # noqa: BLE001
            return {}
    return _cached_get("shipyard:books:wallets", read)


def live_orders() -> list:
    """The corporation's open market orders (cached 5 minutes); [] without a token with the orders scope."""
    import datetime as dt

    def read():
        try:
            from allianceauth.eveonline.models import EveCharacter
            from esi.models import Token

            from . import esi, ledger
            ids = list(EveCharacter.objects.filter(corporation_id=ledger.corp_id()).values_list("character_id", flat=True))
            tok = Token.objects.filter(character_id__in=ids).require_scopes(["esi-markets.read_corporation_orders.v1"]).require_valid().order_by("-created").first()
            if tok is None:
                return []
            rows = esi._authed(f"/corporations/{ledger.corp_id()}/orders/", tok.valid_access_token()).json() or []
            return [{"type_id": int(r["type_id"]), "is_buy": bool(r.get("is_buy_order")), "price": float(r["price"]),
                     "remain": int(r["volume_remain"]), "total": int(r["volume_total"]), "escrow": float(r.get("escrow") or 0),
                     "location_id": int(r["location_id"]), "division": int(r.get("wallet_division") or 1),
                     "issued": dt.datetime.fromisoformat(str(r["issued"]).replace("Z", "+00:00"))} for r in rows]
        except Exception:  # noqa: BLE001
            return []
    return [dict(o) for o in _cached_get("shipyard:books:orders", read)]


def refresh() -> list[str]:
    """Read EVE now: the projects, the corp's journal and transactions, the structure corp's journal."""
    from django.core.cache import cache

    from . import ledger, wallet as structure_wallet
    cache.delete_many(["shipyard:books:wallets", "shipyard:books:orders", "shipyard:books:history"])
    out = []
    for label, fn in (("projects", projects.refresh), ("corporation journal", ledger.refresh), ("structure income", structure_wallet.refresh)):
        try:
            fn()
            out.append(f"{label}: read")
        except Exception as exc:  # noqa: BLE001
            out.append(f"{label}: {exc}")
    return out
