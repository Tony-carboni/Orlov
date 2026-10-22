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
from ..models import BookDirectSale, BookIgnoredEntry, BooksBaseline, BookStock, CorpJournalEntry, CorpProject, CorpWalletTransaction, MarketLocation, Ore, PriceSnapshot
from .directsales import CODE_RE
from . import projectbooks, projects, reprocessing

M = 1e6
FEES = ("brokers_fee", "transaction_tax", "market_provider_tax")
# an LP purchase: "50.000 LP", "15000 LP", "57k State protectorate LP", "1.2M LP", or "LP 16000" (the owner's reasons, 2026-10-19 to -22)
LP_REASON = re.compile(r"(\d[\d.,]*)\s*([kKmM])?(?:\s+[A-Za-z][^\d]*?)?\s*\bLP\b|\bLP\b\s*(\d[\d.,]*)\s*([kKmM])?", re.I)


def lp_units_from(reason) -> int | None:
    """The LP a withdrawal's reason names, or None when it names none."""
    m = LP_REASON.search(reason or "")
    if not m:
        return None
    number, suffix = (m.group(1) or m.group(3)), (m.group(2) or m.group(4) or "")
    scale = {"k": 1_000, "m": 1_000_000}.get(suffix.lower(), 1)
    if scale > 1 and re.fullmatch(r"\d+[.,]\d{1,2}", number):
        return int(round(float(number.replace(",", ".")) * scale))
    return int(re.sub(r"[.,]", "", number)) * scale
# "direct sale ..." or, since EVE's reason field holds 40 characters, "ds ..." (owner's test, 2026-10-21)
DIRECT_SALE = re.compile(r"(?:direct\s+sale|^\s*ds\b)\s*[:\-]?\s*(.*)", re.I)
ITEM_LEAD_QTY = re.compile(r"^(\d[\d.,]*)\s*([kKmM])?\s*[x×]?\s+(.+)$")   # "2,388 Zero-Point Condensate", "719k veld", "1.2M trit"
ITEM_TRAIL_QTY = re.compile(r"^(.+?)\s+[x×]\s*(\d[\d.,]*)\s*([kKmM])?$")  # "Zero-Point Condensate x2388" (names may end in digits, so only with an x)


def _qty(number: str, suffix) -> int:
    """'2,388' -> 2388; '719k' -> 719000; '1.2M' -> 1200000 (a dot before 1 or 2 digits with k/M is a decimal, else a thousands separator)."""
    scale = {"k": 1_000, "m": 1_000_000}.get((suffix or "").lower(), 1)
    if scale > 1 and re.fullmatch(r"\d+[.,]\d{1,2}", number):
        return int(round(float(number.replace(",", ".")) * scale))
    return int(re.sub(r"[.,]", "", number)) * scale


def parse_direct_sale_items(text) -> list:
    """'2,388 Zero-Point Condensate, Crystalline Isogen-10' -> [(2388, 'Zero-Point Condensate'), (None, 'Crystalline Isogen-10')].
    A quantity stands before the name (thousands separators allowed) or after it with an x; without one, every unit held."""
    out = []
    # split on ; / and / commas, but not a comma that is a thousands separator (followed by exactly three digits)
    for part in re.split(r"\s*;\s*|\s+and\s+|\s*,(?!\d{3}(?!\d))\s*", text or ""):
        part = part.strip().strip(".")
        if not part:
            continue
        m = ITEM_LEAD_QTY.match(part)
        if m:
            out.append((_qty(m.group(1), m.group(2)), m.group(3).strip()))
            continue
        m = ITEM_TRAIL_QTY.match(part)
        if m:
            out.append((_qty(m.group(2), m.group(3)), m.group(1).strip()))
            continue
        out.append((None, part))
    return out


def direct_sale(entry_id: int, items: str, note: str = "", cid=None):
    """Record (or replace) what a direct-sale deposit sold, for a reason that does not name the items."""
    cid = cid or projects.corp_id()
    row, _ = BookDirectSale.objects.update_or_create(corporation_id=cid, entry_id=int(entry_id), defaults={"items": items[:500], "note": note[:200]})
    return row


def _take_until(queue, need, until):
    """Use `need` units from a deque of [t, qty, unit_cost, ...] lots that existed by `until`, oldest first."""
    cost = taken = 0.0
    while need > 1e-9 and queue and queue[0][0] <= until:
        lot = queue[0]
        take = min(need, lot[1])
        cost += take * lot[2]
        taken += take
        lot[1] -= take
        need -= take
        if lot[1] <= 1e-9:
            queue.popleft()
    return cost, taken


def _apply_direct_sales(direct_sales, led, cid, until=None) -> None:
    """Take the items each direct sale names out of the project-goods lots (an ore through its minerals, as the
    ledger stores them). Writes cost, removed and unmatched into each sale's dict. Stock-take write-offs (code
    WO-..., no deposit) are added to the list at their moment with no cash: the lots leave at cost."""
    overrides = dict(BookDirectSale.objects.filter(corporation_id=cid, entry_id__isnull=False).exclude(items="").values_list("entry_id", "items"))
    registered = {s.code.upper(): s for s in BookDirectSale.objects.filter(corporation_id=cid).exclude(code="")}
    for wo in BookDirectSale.objects.filter(corporation_id=cid, code__startswith="WO-", matched_at__isnull=False):
        if until is not None and wo.matched_at > until:
            continue
        direct_sales.append({"t": wo.matched_at, "who": wo.created_by or "stock take", "reason": wo.note, "amount": 0.0, "entry_id": None,
                             "code": wo.code, "item": "", "writeoff": True})
    lots, names, ores, yields = led["lots"], led["names"], led.get("ores", {}), led.get("yields", {})

    def take_ore(ore, qty, until):
        batches = qty / float(ore.portion_size or 1)
        y = yields.get(ore.type_id) or reprocessing.yield_for(ore)
        cost = 0.0
        for m, q in (ore.materials or {}).items():
            c, _ = _take_until(lots[int(m)], batches * float(q) * y, until)
            cost += c
        return cost
    by_name = {n.lower(): tid for tid, n in names.items()}
    ore_by_name = {o.name.lower(): o for o in ores.values()}

    aliases = {k.lower(): v.lower() for k, v in app_settings.SHIPYARD_BOOKS_ITEM_ALIASES.items()}

    def resolve(table, name):
        """An exact name, an abbreviation from the settings, a unique prefix, or the shortest name containing the text."""
        key = aliases.get(name.lower(), name.lower())
        if key in table:
            return table[key]
        hits = [k for k in table if k.startswith(key)]
        if not hits:
            hits = [k for k in table if key in k]
        if not hits:
            return None
        return table[min(hits, key=len)]

    for d in sorted(direct_sales, key=lambda d: d["t"]):
        d["cost"], d["removed"], d["unmatched"] = 0.0, [], []
        sale = registered.get(d.get("code") or "")
        if sale is not None:
            # a sale registered on the Finance tab: its quoted lines are what left the stock
            if sale.entry_id is None and not d.get("writeoff"):
                sale.entry_id, sale.matched_at = d["entry_id"], d["t"]
                sale.save(update_fields=["entry_id", "matched_at"])
            for ln in sale.lines or []:
                tid, qty = int(ln["type_id"]), float(ln["qty"])
                ore = ores.get(tid) or (Ore.objects.filter(type_id=tid).first() if ln.get("is_ore") else None)
                if ore is not None and tid not in lots:
                    d["cost"] += take_ore(ore, qty, d["t"])
                    d["removed"].append(f"{qty:,.0f} {ln['name']}")
                else:
                    cost, taken = _take_until(lots[tid], qty, d["t"])
                    d["cost"] += cost
                    d["removed"].append(f"{taken:,.0f} {ln['name']}")
            d["item"] = d["item"] or sale.code
            d["registered"] = sale
            continue
        text = overrides.get(d["entry_id"]) or d["item"]
        for qty, name in parse_direct_sale_items(text):
            ore = resolve(ore_by_name, name)
            if ore is not None and ore.type_id not in lots:
                if qty is None:
                    d["unmatched"].append(f"{name} (an ore needs a quantity)")
                    continue
                d["cost"] += take_ore(ore, qty, d["t"])
                d["removed"].append(f"{qty:,} {ore.name}")
                continue
            tid = resolve(by_name, name) if ore is None else ore.type_id
            if tid is None or tid not in lots:
                d["unmatched"].append(name)
                continue
            want = float(qty) if qty is not None else sum(r[1] for r in lots[tid] if r[0] <= d["t"])
            cost, taken = _take_until(lots[tid], want, d["t"])
            d["cost"] += cost
            d["removed"].append(f"{taken:,.0f} {names.get(tid, name)}")
            if qty is not None and taken + 1e-6 < qty:
                d["unmatched"].append(f"{name}: only {taken:,.0f} of {qty:,} were held")
FUEL_BLOCKS = {4051: "Nitrogen", 4246: "Hydrogen", 4247: "Helium", 4312: "Oxygen"}
DIRECTOR_DIVISION = 7


def baseline():
    """The newest period (its start and opening figures); the loan comes from the oldest, the budget baseline."""
    return BooksBaseline.objects.order_by("-taken_at").first()


def budget():
    return BooksBaseline.objects.order_by("taken_at").first()


def _pool_at(cid, when):
    """Reward ISK in the active projects at a past moment, from the hourly snapshots: per project the last
    snapshot at or before `when`; a project without one by then did not exist yet."""
    from ..models import ProjectSnapshot
    latest = {}
    for snap in ProjectSnapshot.objects.filter(project__corporation_id=cid, taken_at__lte=when).order_by("taken_at", "id"):
        latest[snap.project_id] = snap
    return sum(snap.reward_remaining for snap in latest.values() if snap.state == "Active")


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


CORRECTION = re.compile(r"correct", re.I)


def _drop_corrections(journal):
    """A deposit whose reason says "correction" pays back a withdrawal of the same amount made shortly
    before (a mistyped LP purchase, for example): both lines leave the books, nothing else changes."""
    out = list(journal)
    for i, e in enumerate(journal):
        if e.ref_type != "player_donation" or e.amount <= 0 or not CORRECTION.search(e.reason or ""):
            continue
        for j in range(i - 1, -1, -1):
            w = journal[j]
            if (w.ref_type == "corporation_account_withdrawal" and abs(w.amount + e.amount) < 1
                    and (e.date - w.date).total_seconds() <= 6 * 3600 and w in out):
                out.remove(w)
                out.remove(e)
                break
    return out


def _drop_ignored(journal, cid):
    """Leave out the lines flagged in the admin (BookIgnoredEntry) and those whose reason matches
    SHIPYARD_BOOKS_IGNORE_REASONS. Returns (journal, {"count", "net", "lines"})."""
    import copy

    flagged = {(r.division, r.entry_id): (r.reason, r.amount) for r in BookIgnoredEntry.objects.filter(corporation_id=cid)}
    patterns = [re.compile(p, re.I) for p in app_settings.SHIPYARD_BOOKS_IGNORE_REASONS]
    kept, out = [], []
    for e in journal:
        why, part = flagged.get((e.division, e.entry_id), (None, None))
        if why is None and e.reason and any(p.search(e.reason) for p in patterns):
            why = f"reason: {e.reason}"
        if why is None:
            kept.append(e)
        elif part is not None and 0 < part < abs(e.amount):
            # only part of the line leaves the books; the rest stays, with the line's own sign
            sign = 1.0 if e.amount >= 0 else -1.0
            rest = copy.copy(e)
            rest.amount = e.amount - sign * part
            kept.append(rest)
            out.append([e.date, e.ref_type, sign * part, f"{why} ({part:,.0f} of {abs(e.amount):,.0f})"])
        else:
            out.append([e.date, e.ref_type, e.amount, why])
    return kept, {"count": len(out), "net": sum(r[2] for r in out), "lines": out}


def ignore_entries(entry_ids, reason: str, cid=None, division: int = 1, amount=None) -> int:
    """Flag journal lines by id (the corp's division 1 unless told otherwise). `amount` leaves out only that much
    of each line (positive ISK); the rest stays in the books. Returns how many were new."""
    cid = cid or projects.corp_id()
    n = 0
    for entry_id in entry_ids:
        row, created = BookIgnoredEntry.objects.get_or_create(corporation_id=cid, division=division, entry_id=int(entry_id),
                                                              defaults={"reason": reason[:200], "amount": amount})
        if not created and (row.amount != amount or row.reason != reason[:200]):
            row.amount, row.reason = amount, reason[:200]
            row.save(update_fields=["amount", "reason"])
        n += 1 if created else 0
    return n


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
    first = budget()
    if now is not None:
        # the position at a past moment: the period in force then
        b = BooksBaseline.objects.filter(taken_at__lte=now).order_by("-taken_at").first() or first
    cid = projects.corp_id()
    base = b.taken_at          # the period's start: movements count from here
    origin = first.taken_at    # the budget baseline: stock and goods count from here (position)
    loan = first.loan
    divisions = list(app_settings.SHIPYARD_BOOKS_DIVISIONS)
    journal = list(CorpJournalEntry.objects.filter(corporation_id=cid, date__gte=origin, division__in=divisions).order_by("date", "entry_id"))
    if now is not None:
        journal = [e for e in journal if e.date <= now]
    journal = _drop_corrections(journal)
    journal, ignored = _drop_ignored(journal, cid)
    cut = journal[-1].date if journal else base
    if cut < base:
        cut = base
    # a market journal line names its transaction in context_id (the transaction's journal_ref_id points elsewhere)
    txs = {t.transaction_id: t for t in CorpWalletTransaction.objects.filter(corporation_id=cid, date__gte=origin, date__lte=cut)}
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
    purchase_left = {s.id: s.units * (s.unit_cost or 0) for s in batches if s.bought_at > origin and not _is_conversion(s)}
    lp_units, lp_cost = b.lp_units, b.lp_cost  # the LP held at the period's start, then what the period bought
    period_sales = set()  # stock sales inside the period (the profit moves); all sales feed the position and the months
    for e in journal:
        inp = e.date >= base  # inside the period: a movement; before it: only the position (stock, LP, months)
        if inp:
            cash[e.division] += e.amount
        rt = e.ref_type
        t = txs.get(e.context_id) if e.context_id_type == "market_transaction_id" else None
        if rt == "market_transaction":
            if e.amount >= 0:
                if t is None:
                    if inp:
                        untyped_sales += e.amount
                elif t.type_id in stock_types:
                    stock_sales.append([t.date, t.type_id, t.quantity, e.amount, e.entry_id])
                    if inp:
                        period_sales.add(e.entry_id)
                else:
                    if inp:
                        goods_sales[names.get(t.type_id, f"type {t.type_id}")] += e.amount
                    goods_sale_entries.append([e.entry_id, t.type_id, e.date])
            elif t is not None:
                market_buys.append([t.date, t.type_id, t.quantity, -e.amount, inp])
            elif inp:
                other_buys += e.amount
        elif rt == "market_escrow" and t is not None and t.is_buy and e.amount < 0:
            market_buys.append([t.date, t.type_id, t.quantity, -e.amount, inp])  # a buy order that filled at once
        elif rt == "market_escrow":
            if inp:
                escrow += e.amount
        elif rt in FEES:
            if inp:
                fees += e.amount
            if rt == "transaction_tax":
                tax_by_entry[e.entry_id] = e.amount
            elif rt == "brokers_fee":
                broker_lines.append([e.date, e.amount])
        elif rt == "project_payouts":
            if inp:
                project_net += e.amount
        elif rt == "lp_store":
            if inp:
                lp_store_paid += e.amount
        elif rt == "player_donation" and e.amount > 0:
            if not inp:
                continue
            m = DIRECT_SALE.search(e.reason or "")
            c = CODE_RE.search(e.reason or "")
            row = {"t": e.date, "who": names.get(e.first_party_id, str(e.first_party_id)), "reason": e.reason, "amount": e.amount, "entry_id": e.entry_id,
                   "code": c.group(0).upper() if c else ""}
            (direct_sales if (m or c) else deposits).append({**row, "item": m.group(1).strip() if m else ""})
        elif rt == "corporation_account_withdrawal":
            if e.first_party_id == cid and e.second_party_id == cid:
                # between wallet divisions: within 1-6 it nets to zero; to division 7 it leaves the books
                if inp:
                    transfers_out += e.amount
                continue
            units = lp_units_from(e.reason) if e.amount < 0 else None
            if units:
                lp_purchases.append([e.date, units, -e.amount, names.get(e.second_party_id, str(e.second_party_id))])
                if inp:
                    lp_units += units
                    lp_cost += -e.amount
                continue
            paid = next((bid for bid, left in purchase_left.items() if left and abs(-e.amount - left) <= max(1.0, 0.001 * left)), None)
            if paid is not None and e.amount < 0:
                if inp:
                    stock_paid.append([paid, -e.amount])
                purchase_left[paid] = 0
                continue
            if inp:
                payouts.append({"t": e.date, "to": names.get(e.second_party_id, str(e.second_party_id)), "reason": e.reason, "amount": e.amount})
        elif inp:
            others[rt] += e.amount

    # --- stock: every lot at cost, first in, first out ---------------------------------------------
    lp_avg = (lp_cost / lp_units) if lp_units else 0.0
    lots = defaultdict(deque)
    stock_base = 0.0
    events = []  # (t, order, kind, payload): purchases and redemptions before the sales of the same moment
    for s in batches:
        events.append((s.bought_at, 1 if _is_conversion(s) else 0, "batch", s))
    for t, tid, qty, cost, inp in market_buys:
        events.append((t, 0, "buy", (tid, qty, cost)))
    for t, tid, qty, revenue, entry_id in stock_sales:
        tax = tax_by_entry.get(entry_id + 1, tax_by_entry.get(entry_id - 1, 0.0))
        events.append((t, 2, "sale", (tid, qty, revenue, tax, entry_id in period_sales)))
    sold = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])  # type -> [qty, revenue, cost, sales tax]
    sold_period = defaultdict(lambda: [0.0, 0.0, 0.0])  # type -> [qty, revenue, cost] inside the period (the profit moves)
    sold_month = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])  # (YYYY-MM, type) -> [qty, revenue, cost, sales tax]
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
            tid, qty, revenue, tax, inp = p
            cost, _ = _take(lots[tid], float(qty))
            s = sold[tid]
            s[0] += qty
            s[1] += revenue
            s[2] += cost
            s[3] += tax
            if inp:
                sp = sold_period[tid]
                sp[0] += qty
                sp[1] += revenue
                sp[2] += cost
            sm = sold_month[(t.strftime("%Y-%m"), tid)]
            sm[0] += qty
            sm[1] += revenue
            sm[2] += cost
            sm[3] += tax
        elif not _is_conversion(p):
            lots[p.type_id].append([t, float(p.units), p.unit_cost or 0.0])
            if t <= origin:
                stock_base += p.units * (p.unit_cost or 0.0)
        else:
            lp_value = p.lp_used * lp_avg
            input_cost, input_taken = _take(lots[p.input_type_id], float(p.input_units)) if p.input_type_id and p.input_units else (0.0, 0.0)
            if p.input_type_id:
                used_units[p.input_type_id][0] += input_taken
                used_units[p.input_type_id][1] += input_cost
            total = lp_value + input_cost + p.isk_paid
            lots[p.type_id].append([t, float(p.units), total / p.units if p.units else 0.0])
            if t >= base:
                lp_used += p.lp_used
            conversions.append({"type_id": p.type_id, "t": t, "in_period": t >= base, "name": p.name, "units": p.units, "lp": p.lp_used, "lp_value": lp_value, "input": names.get(p.input_type_id, ""),
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
    market_bought = sum(c for _, _, _, c, inp in market_buys if inp)
    lp_left = lp_cost - lp_used * lp_avg

    # --- project goods still held, split at the baseline -----------------------------------------
    led = projectbooks.ledger(cid, until=cut)
    prices, pnames = led["prices"], led["names"]
    _apply_direct_sales(direct_sales, led, cid, until=now)  # the lots they sold leave before the count below; a stock take counts on a live sheet whatever its last journal line
    held, held_value, older_cost, older_value = defaultdict(float), 0.0, 0.0, 0.0
    held_items = defaultdict(lambda: [0.0, 0.0, 0.0, "item"])  # item -> [units, cost, value at Jita buy, origin], bought since the baseline
    for tid, queue in led["lots"].items():
        if tid in stock_types:
            continue  # bought on the market or kept as stock: counted above
        name = pnames.get(tid, str(tid))
        for t, qty, cost, *rest in queue:
            lot_origin = rest[0] if rest else "item"
            if t >= origin:
                held[name] += qty * cost
                held_value += qty * prices.get(tid, 0.0)
                hi = held_items[name]
                hi[0] += qty
                hi[1] += qty * cost
                hi[2] += qty * prices.get(tid, 0.0)
                hi[3] = lot_origin
            else:
                older_cost += qty * cost
                older_value += qty * prices.get(tid, 0.0)
    held_total = sum(held.values())

    # --- open orders (EVE now) ---------------------------------------------------------------------
    orders = live_orders() if now is None else []  # the orders of a past moment are not known
    open_escrow = sum(o["escrow"] for o in orders if o["is_buy"] and o["issued"] <= cut)
    order_names = _names([o["type_id"] for o in orders if o["type_id"] not in names])
    for o in orders:
        o["name"] = names.get(o["type_id"]) or order_names.get(o["type_id"], f"type {o['type_id']}")
        lot = next((s for s in stock_lines if s["type_id"] == o["type_id"]), None)
        o["unit_cost"] = lot["unit_cost"] if lot else None
        o["value"] = o["remain"] * o["price"]

    # --- position --------------------------------------------------------------------------------
    if now is None:
        pool = sum(p.reward_remaining for p in CorpProject.objects.filter(corporation_id=cid, missing=False, state="Active"))
        n_projects = CorpProject.objects.filter(corporation_id=cid, missing=False, state="Active").count()
    else:
        pool = _pool_at(cid, now)
        n_projects = 0
    wallet = b.wallet + cash.get(1, 0.0)
    other_divs = b.other_divs + sum(v for d, v in cash.items() if d != 1)
    assets = wallet + other_divs + pool + stock_now + held_total + lp_left + open_escrow
    result = assets - loan
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
        if d.get("writeoff"):
            moves.append([f"Goods written off, stock take of {_when(d['t'])}", 0.0,
                          f"{d.get('cost', 0.0) / M:.1f} M of project goods left the books at cost: sold earlier without a record" + (f"; {d['reason']}" if d.get("reason") else "")])
            continue
        what = ", ".join(d.get("removed") or []) or (d["item"] or "items not named")
        note = f"Deposited by {d['who']}, {_when(d['t'])}; {d.get('cost', 0.0) / M:.1f} M of stock left the books"
        if d.get("unmatched"):
            note += "; not matched: " + ", ".join(d["unmatched"]) + " (name the items in the reason, or in the admin under Shipyard → direct sales)"
        moves.append([f"Goods sold directly ({what})", d["amount"], note])
    for tid, (qty, revenue, cost) in sold_period.items():
        if qty:
            moves.append([f"{names.get(tid, tid)} sold, profit over its cost", revenue - cost,
                          f"{qty:,.0f} units for {revenue / M:.1f} M, less what they cost = {cost / M:.1f} M"])
    if escrow:
        moves.append(["Escrow of corporation buy orders", escrow, "Set aside (−) for open buy orders or returned (+); an order placed before the period was not part of its opening"])
    if abs(open_escrow - b.open_escrow) >= 1:
        moves.append(["ISK still in open buy orders", open_escrow - b.open_escrow, "Corporation money waiting in buy orders (section 1), against the period's opening"])
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
    moves.append(["Goods those rewards bought, still held", held_total - b.held, "At cost, as in section 1" + (f"; {b.held / M:.1f} M of it was already held at the period's start" if b.held else "")])
    if market_bought:
        bought_names = sorted({names.get(tid, str(tid)) for _, tid, _, _, inp in market_buys if inp})
        moves.append(["Bought on the market", 0.0, f"{market_bought / M:.1f} M paid for {', '.join(bought_names)}, held as stock at cost or used below"])
    all_conv = list(conversions)
    conversions = [c for c in conversions if c["in_period"]]
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
    if lp_cost - b.lp_cost:
        moves.append(["LP bought", 0.0, f"{(lp_cost - b.lp_cost) / M:.1f} M paid for {lp_units - b.lp_units:,} LP, held at cost until used"])
    explained = sum(m[1] for m in moves)
    gap = (result - b.opening_result) - explained
    goods_tax_month = defaultdict(float)  # (YYYY-MM, type) -> sales tax of project-goods sales
    for entry_id, tid, when in goods_sale_entries:
        goods_tax_month[(when.strftime("%Y-%m"), tid)] += tax_by_entry.get(entry_id + 1, tax_by_entry.get(entry_id - 1, 0.0))
    sale_prices = defaultdict(set)
    for t in txs.values():
        if not t.is_buy:
            sale_prices[t.type_id].add(t.unit_price)
    project_bb = _project_buybacks(cid, base, cut, led, goods_tax_month, _broker_split(broker_lines, orders, sale_prices)[1], stock_types,
                                   held_items, older_cost, older_value, paid_members, direct_sales)
    all_conversions = all_conv
    # the corporation's LP change by change (owner, 2026-10-22): purchases from the journal, conversions from the stock batches
    lp_events = []
    for t, units, isk, to in lp_purchases:
        lp_events.append({"t": t, "lp": units, "isk": isk, "what": f"Bought from {to}: {units:,} LP for {isk / M:.1f} M ({isk / units:,.0f} ISK per LP)" if units else f"Bought from {to}"})
    for c in all_conv:
        if c["lp"]:
            lp_events.append({"t": c["t"], "lp": -c["lp"], "isk": 0.0,
                              "what": f"Converted into {c['units']:,} {c['name']}" + (f" with {c['input_units']:,.0f} {c['input']}" if c["input_units"] else "")})
    lp_events.sort(key=lambda e: e["t"])
    running = 0
    for e in lp_events:
        running += e["lp"]
        e["balance"] = running
    buyback = _buyback(lp_purchases, lp_units, lp_cost, lp_avg, lp_used, lp_left, all_conversions, sold, sold_month, lots, names, orders, broker_lines, sale_prices)
    if abs(gap) >= 1.0:
        moves.append(["Not explained", gap, "The journal and the position differ: a missing journal page or a new kind of entry"])
    outputs = {c["name"] for c in conversions}
    move_groups = _group_moves(moves, outputs)
    asset_groups = _group_assets(wallet, cash, orders, cut, pool, n_projects, stock_lines, held, held_value, lp_units - lp_used, lp_left)

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
    hours = max(0.0, (cut - origin).total_seconds() / 3600)

    return {
        "cut": cut, "base": base, "origin": origin, "loan": loan, "period": b, "opening_result": b.opening_result,
        "since_label": b.source or f"the working-budget baseline of {origin.day} {origin:%B}, {origin:%H:%M} EVE",
        "period_result": result - b.opening_result, "wallet": wallet, "other_divs": other_divs, "pool": pool, "n_projects": n_projects,
        "stock": stock_lines, "stock_now": stock_now, "stock_base": stock_base,
        "held": sorted(held.items(), key=lambda kv: -kv[1]), "held_total": held_total, "held_value": held_value,
        "lp_units": lp_units - lp_used, "lp_cost": lp_left, "lp_bought": lp_units, "open_escrow": open_escrow,
        "assets": assets, "result": result, "moves": moves, "explained": explained, "gap": gap,
        "lots_left": [(tid, pnames.get(tid, str(tid)), sum(r[1] for r in q), sum(r[1] * r[2] for r in q)) for tid, q in led["lots"].items() if sum(r[1] for r in q) > 0],
        "move_groups": move_groups, "asset_groups": asset_groups, "ignored": ignored,
        "director": director, "older": (older_cost, older_value), "structure_income": structure_income,
        "live_books": live_books, "books_now": books_now, "live_ahead": (live_books - books_now) if live_books is not None else None,
        "orders": orders, "buyback": buyback, "project_bb": project_bb, "lp_events": lp_events,
        "fuel_price": fuel_price, "fuel_name": fuel_name, "fuel_rows": fuel_rows, "fuel_paying_bph": paying,
        "fuel_burned": round(hours * paying), "fuel_burned_isk": round(hours * paying) * fuel_price,
        "generated": timezone.now(), "market": market.name if market else "",
    }


def _broker_split(broker_lines, orders, sale_prices=None):
    """Broker fees of listings, by item type and by (month, type): each fee line goes to the order issued
    (or last modified) nearest to it, within 90 seconds. Orders: open ones and EVE's order history."""
    by_type, by_month = defaultdict(float), defaultdict(float)
    listed = list(orders) + order_history()

    def rate(amount, o):
        value = o["price"] * o["total"]
        return (-amount / value) if value else 0.0

    nearest = {}
    for k, (t, amount) in enumerate(broker_lines):
        near = sorted((abs((o["issued"] - t).total_seconds()), i) for i, o in enumerate(listed) if abs((o["issued"] - t).total_seconds()) <= 90)
        nearest[k] = near[0][1] if near else None
    # the usual broker rate, from fees that sit right next to their order (a listing fee is that rate x the order's value)
    rates = sorted(rate(broker_lines[k][1], listed[i]) for k, i in nearest.items() if i is not None and 0.003 < rate(broker_lines[k][1], listed[i]) < 0.05)
    usual = rates[len(rates) // 2] if rates else None
    for k, (t, amount) in enumerate(broker_lines):
        pick = nearest[k]
        if usual and (pick is None or abs(rate(amount, listed[pick]) / usual - 1) > 0.01):
            # a repriced order carries its new time and price: look at orders placed or repriced at or after this fee,
            # valued at the prices that item really sold at (a sell order fills at its listed price)
            fits = []
            for i, o in enumerate(listed):
                if not (-90 <= (o["issued"] - t).total_seconds() <= 12 * 3600):
                    continue
                for price in {o["price"]} | set((sale_prices or {}).get(o["type_id"], ())):
                    value = price * o["total"]
                    if value:
                        fits.append((abs((-amount / value) / usual - 1), i))
            fits.sort()
            if fits and fits[0][0] <= 0.005:
                pick = fits[0][1]
        if pick is not None:
            tid = listed[pick]["type_id"]
            by_type[tid] += amount
            by_month[(t.strftime("%Y-%m"), tid)] += amount
    return by_type, by_month


def _buyback(lp_purchases, lp_units, lp_cost, lp_avg, lp_used, lp_left, conversions, sold, sold_month, lots, names, orders, broker_lines, sale_prices=None) -> dict:
    """LP buybacks and conversions per calendar month (owner, 2026-10-20): LP bought and converted, what it
    was converted into, what those items sold for with their sales tax and broker fees, the net profit,
    and what is still on sell orders with its projected net. Items bought to convert that are not
    converted yet are ordinary stock (section 1)."""
    import datetime as dt

    by_type, by_month = _broker_split(broker_lines, orders, sale_prices)
    products = []
    for c in conversions:
        if c["type_id"] not in products:
            products.append(c["type_id"])
    tax_rate = {}
    for tid in products:
        qty, revenue, cost, tax = sold[tid]
        tax_rate[tid] = (-tax / revenue) if revenue else 0.0
    listed = {}
    for tid in products:
        rows = [o for o in orders if o["type_id"] == tid and not o["is_buy"]]
        units = sum(o["remain"] for o in rows)
        value = sum(o["remain"] * o["price"] for o in rows)
        left_units = sum(r[1] for r in lots[tid])
        left_cost = sum(r[1] * r[2] for r in lots[tid])
        cost_listed = left_cost * units / left_units if left_units else 0.0
        listed[tid] = {"name": names.get(tid, f"type {tid}"), "units": units, "value": value, "price": (value / units) if units else None,
                       "cost": cost_listed, "expected": value * (1 - tax_rate[tid]) - cost_listed, "left": left_units, "left_cost": left_cost}

    months = sorted({t.strftime("%Y-%m") for t, *_ in lp_purchases} | {c["t"].strftime("%Y-%m") for c in conversions}
                    | {m for m, tid in sold_month if tid in products} | {m for m, tid in by_month if tid in products}, reverse=True)
    out = []
    for i, key in enumerate(months):
        bought = [p for p in lp_purchases if p[0].strftime("%Y-%m") == key]
        made = [c for c in conversions if c["t"].strftime("%Y-%m") == key]
        conv = []
        for tid in products:
            rows = [c for c in made if c["type_id"] == tid]
            if rows:
                units = sum(c["units"] for c in rows)
                cost = sum(c["total"] for c in rows)
                conv.append({"name": names.get(tid, f"type {tid}"), "units": units, "cost": cost, "unit_cost": cost / units if units else 0.0,
                             "lp": sum(c["lp"] for c in rows), "lp_value": sum(c["lp_value"] for c in rows),
                             "input_units": sum(c["input_units"] for c in rows), "input": rows[0]["input"],
                             "input_cost": sum(c["input_cost"] for c in rows), "isk": sum(c["isk"] for c in rows)})
        sales = []
        for tid in products:
            qty, revenue, cost, tax = sold_month.get((key, tid), [0.0, 0.0, 0.0, 0.0])
            broker = by_month.get((key, tid), 0.0)
            if qty or broker:
                sales.append({"name": names.get(tid, f"type {tid}"), "sold": qty, "revenue": revenue, "cost": cost, "tax": tax, "broker": broker,
                              "net": revenue - cost + tax + broker})
        latest = i == 0
        still = [v for v in listed.values() if v["units"]] if latest else []
        realised = sum(x["net"] for x in sales)
        expected = sum(v["expected"] for v in still)
        sold_value = sum(x["revenue"] for x in sales)
        cost_sold = sum(x["cost"] for x in sales)
        listed_value = sum(v["value"] for v in still)
        lp_b = sum(p[1] for p in bought)
        isk_b = sum(p[2] for p in bought)
        first = dt.datetime.strptime(key, "%Y-%m")
        out.append({"key": key, "label": f"{first:%B %Y}", "lp_bought": lp_b, "lp_isk": isk_b, "lp_avg": (isk_b / lp_b) if lp_b else None,
                    "purchases": bought, "lp_converted": sum(c["lp"] for c in made), "converted": conv,
                    "converted_cost": sum(c["cost"] for c in conv), "sales": sales, "still": still,
                    "realised": realised, "expected": expected, "total": realised + expected,
                    "sold_value": sold_value, "cost_sold": cost_sold, "listed_value": listed_value, "output_value": sold_value + listed_value, "latest": latest})
    buying = [o for o in orders if o["is_buy"]]
    realised = sum(m["realised"] for m in out)
    expected = sum(m["expected"] for m in out)
    sold_value = sum(m["sold_value"] for m in out)
    cost_sold = sum(m["cost_sold"] for m in out)
    return {"months": out, "lp_units": lp_units, "lp_cost": lp_cost, "lp_avg": lp_avg, "lp_used": lp_used,
            "lp_left": lp_units - lp_used, "lp_left_value": lp_left, "buying": buying,
            "realised": realised, "expected": expected, "total": realised + expected,
            # margin on what sold (owner, 2026-10-22): the sale price against what the conversion cost, nothing held counted
            "sold_value": sold_value, "cost_sold": cost_sold, "margin": ((sold_value - cost_sold) / cost_sold) if cost_sold else None,
            "outside": sum(c["isk"] for c in conversions if c["outside"]),
            "active": bool(lp_purchases or conversions)}


def _project_buybacks(cid, base, cut, led, goods_tax_month, brokers_month, stock_types, held_items, older_cost, older_value, paid_members, direct_sales=()) -> dict:
    """Project buybacks per calendar month (owner, 2026-10-20), condensed: two lines per month, ore and
    ice (asteroid, ice, moon and abyssal ore the projects buy, sold through what they reprocess into) and
    other items (sold as delivered), each with what the projects paid members, what sold with sales tax
    and broker fees, the net profit, and what is still held with a projected net; the items behind a click."""
    import datetime as dt

    from ..models import Ore

    def month(when):
        return when.strftime("%Y-%m")

    names_of = {}

    def name_of(tid):
        if tid not in names_of:
            names_of[tid] = led["names"].get(tid) or _names([tid]).get(tid, str(tid))
        return names_of[tid]

    stock_names = {name_of(tid) for tid in stock_types}
    bare = {int(m[1]) for m in led["matches"] + led["others"] if str(m[1]).isdigit()}
    fixed = _names(bare) if bare else {}

    def clean(n):
        return fixed.get(int(n), n) if str(n).isdigit() else n

    since = base.replace(second=0, microsecond=0)
    matches = [[dt.datetime.fromisoformat(w), clean(n), rev, cost, qty, (rest[0] if rest else "item")] for w, n, rev, cost, qty, *rest in led["matches"]]
    others = [[dt.datetime.fromisoformat(w), clean(n), rev] for w, n, rev in led["others"]]
    matches = [m for m in matches if m[0] >= since and m[1] not in stock_names]
    others = [o for o in others if o[0] >= since and o[1] not in stock_names]
    sold_origin = {m[1]: m[5] for m in matches}

    pays = [e for e in projectbooks.payout_events(cid) if base <= e["t"] <= cut]
    type_names = _names({e["type_id"] for e in pays if e["type_id"]})
    ore_types = set(Ore.objects.filter(type_id__in=[e["type_id"] for e in pays if e["type_id"]]).values_list("type_id", flat=True))

    fees = defaultdict(lambda: [0.0, 0.0])  # (month, item) -> [sales tax, broker]
    for (mo, tid), tax in goods_tax_month.items():
        fees[(mo, name_of(tid))][0] += tax
    for (mo, tid), fee in brokers_month.items():
        if tid not in stock_types:
            fees[(mo, name_of(tid))][1] += fee

    direct = [d for d in direct_sales if d["t"] >= since and not d.get("writeoff")]
    months = sorted({month(e["t"]) for e in pays} | {month(m[0]) for m in matches} | {month(o[0]) for o in others} | {month(d["t"]) for d in direct}, reverse=True)
    all_tax = sum(v[0] for v in fees.values())
    all_revenue = sum(m[2] for m in matches) + sum(o[2] for o in others)
    tax_rate = (-all_tax / all_revenue) if all_revenue else 0.0
    GROUPS = (("ore", "Ore and ice"), ("item", "Other items"))

    def blank():
        return {"delivered": 0.0, "paid": 0.0, "members": set(), "sold": 0.0, "revenue": 0.0, "cost": 0.0, "tax": 0.0, "broker": 0.0,
                "unmatched": 0.0, "held_units": 0.0, "held_cost": 0.0, "held_value": 0.0}

    out = []
    for i, key in enumerate(months):
        items = defaultdict(blank)  # (group, item) -> figures
        for e in pays:
            if month(e["t"]) == key:
                nm = type_names.get(e["type_id"], e["project"]) if e["type_id"] else f"{e['project']} (no item)"
                g = "ore" if e["type_id"] in ore_types else "item"
                row = items[(g, nm)]
                row["delivered"] += e["units"]
                row["paid"] += e["isk"]
                row["members"].add(e["member"])
        for when, nm, rev, cost, qty, origin in matches:
            if month(when) == key:
                row = items[(origin, nm)]
                row["sold"] += qty
                row["revenue"] += rev
                row["cost"] += cost
        for when, nm, rev in others:
            if month(when) == key and rev >= 0.05e6:
                items[(sold_origin.get(nm, "item"), nm)]["unmatched"] += rev
        for (g, nm), row in items.items():
            tax, broker = fees.get((key, nm), [0.0, 0.0])
            rev_all = row["revenue"] + row["unmatched"]
            share = (row["revenue"] / rev_all) if rev_all else 0.0  # fees in proportion to the part that came from projects
            row["tax"] = tax * share
            row["broker"] = broker * share
        latest = i == 0
        if latest:
            for nm, (units, cost, value, origin) in held_items.items():
                if cost >= 0.05e6:
                    row = items[(origin, nm)]
                    row["held_units"] += units
                    row["held_cost"] += cost
                    row["held_value"] += value
        groups = []
        for g, label in GROUPS:
            rows = []
            for (gg, nm), row in sorted(items.items(), key=lambda kv: -(kv[1]["revenue"] + kv[1]["paid"])):
                if gg != g:
                    continue
                net = row["revenue"] - row["cost"] + row["tax"] + row["broker"]
                expected = row["held_value"] * (1 - tax_rate) - row["held_cost"] if row["held_cost"] else 0.0
                rows.append({"name": nm, "delivered": row["delivered"], "paid": row["paid"], "members": len(row["members"]),
                             "sold": row["sold"], "revenue": row["revenue"], "cost": row["cost"], "tax": row["tax"], "broker": row["broker"],
                             "fees": row["tax"] + row["broker"], "net": net, "pct": (net / row["cost"]) if row["cost"] else None,
                             "unmatched": row["unmatched"], "held_units": row["held_units"], "held_cost": row["held_cost"],
                             "held_value": row["held_value"], "expected": expected})
            if not rows:
                continue
            tot = {k: sum(r[k] for r in rows) for k in ("delivered", "paid", "sold", "revenue", "cost", "tax", "broker", "fees", "net", "unmatched", "held_units", "held_cost", "held_value", "expected")}
            members = set()
            for (gg, nm), row in items.items():
                if gg == g:
                    members |= row["members"]
            groups.append({"key": g, "label": label, "id": f"pb-{key}-{g}", "rows": rows, "members": len(members),
                           "pct": (tot["net"] / tot["cost"]) if tot["cost"] else None, "total": tot["net"] + tot["expected"], **tot})
        # direct sales of the month (owner, 2026-10-21): one line, the deposits against what the projects paid for the goods
        sales = [d for d in direct if month(d["t"]) == key]
        if sales:
            rows = [{"name": f"{_when(d['t'])}: {', '.join(d.get('removed') or []) or d['item'] or 'items not named'}", "delivered": 0.0, "paid": 0.0, "members": 0,
                     "sold": 0.0, "revenue": d["amount"], "cost": d.get("cost", 0.0), "tax": 0.0, "broker": 0.0, "fees": 0.0,
                     "net": d["amount"] - d.get("cost", 0.0), "pct": ((d["amount"] - d.get("cost", 0.0)) / d["cost"]) if d.get("cost") else None,
                     "unmatched": 0.0, "held_units": 0.0, "held_cost": 0.0, "held_value": 0.0, "expected": 0.0} for d in sales]
            tot = {k: sum(r[k] for r in rows) for k in ("delivered", "paid", "sold", "revenue", "cost", "tax", "broker", "fees", "net", "unmatched", "held_units", "held_cost", "held_value", "expected")}
            groups.append({"key": "direct", "label": "Direct sale of goods", "id": f"pb-{key}-direct", "rows": rows, "members": 0,
                           "pct": (tot["net"] / tot["cost"]) if tot["cost"] else None, "total": tot["net"], **tot})
        paid_total = sum(g["paid"] for g in groups)
        realised = sum(g["net"] for g in groups)
        expected = sum(g["expected"] for g in groups)
        sold_value = sum(g["revenue"] for g in groups)
        cost_sold = sum(g["cost"] for g in groups)
        members = set()
        for row in items.values():
            members |= row["members"]
        first = dt.datetime.strptime(key, "%Y-%m")
        out.append({"key": key, "label": f"{first:%B %Y}", "groups": groups, "paid_total": paid_total, "members": len(members),
                    "sold_value": sold_value, "cost_sold": cost_sold, "fees": sum(g["fees"] for g in groups),
                    "realised": realised, "pct": (realised / cost_sold) if cost_sold else None,
                    "held_cost": sum(g["held_cost"] for g in groups), "held_value": sum(g["held_value"] for g in groups),
                    "expected": expected, "total": realised + expected, "latest": latest})
    realised = sum(m["realised"] for m in out)
    expected = sum(m["expected"] for m in out)
    cost_sold = sum(m["cost_sold"] for m in out)
    sold_value = sum(m["sold_value"] for m in out)
    return {"months": out, "paid_total": sum(m["paid_total"] for m in out), "paid_pool": paid_members,
            "realised": realised, "expected": expected, "total": realised + expected,
            "pct": (realised / cost_sold) if cost_sold else None,
            # margin on what sold (owner, 2026-10-22): the sale price, market or direct, against what the projects paid; nothing held counted
            "sold_value": sold_value, "cost_sold": cost_sold, "margin": ((sold_value - cost_sold) / cost_sold) if cost_sold else None,
            "held": sum(v[1] for v in held_items.values()), "held_value": sum(v[2] for v in held_items.values()),
            "older": older_cost, "older_value": older_value, "tax_rate": tax_rate,
            "active": bool(out)}


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


MOVE_GROUPS = [
    ("project_sales", "Project buyback sales", "What the corporation sold of the goods its projects bought from members"),
    ("project_rewards", "Project buyback rewards to members", "ISK the projects paid members, and the goods those rewards bought that are still held"),
    ("lp", "LP conversion", "LP bought, what the LP store gave for it, and the sales of those items"),
    ("stock", "Stock sales", "Stock bought to sell on (Heavy Water), and its sales"),
    ("market", "Market orders and fees", "Escrow of buy orders, items bought on the market, broker fees and sales tax"),
    ("transfers", "Transfers, deposits and payouts", "ISK moved into or out of the corporation's wallets by hand"),
    ("gap", "Not explained", ""),
]


def _group_moves(moves, outputs) -> list:
    """Section 2 by category (owner, 2026-10-20): each movement lands in one group; the groups add up to the result."""
    def key(label):
        if label.startswith("Project goods sold") or label.startswith("Goods sold directly"):
            return "project_sales"
        if label.startswith("Project rewards paid") or label.startswith("Goods those rewards bought"):
            return "project_rewards"
        if label.startswith("LP store:") or label.startswith("Paid in the LP store") or label == "LP bought":
            return "lp"
        if label.endswith("sold, profit over its cost"):
            return "lp" if label[: -len(" sold, profit over its cost")] in outputs else "stock"
        if label == "Stock bought":
            return "stock"
        if label.startswith("Escrow of") or label.startswith("ISK still in open buy orders") or label.startswith("Broker fees") or label.startswith("Bought on the market"):
            return "market"
        if label == "Not explained":
            return "gap"
        return "transfers"
    groups = {k: {"key": k, "label": label, "note": note, "id": f"mv-{k}", "rows": [], "total": 0.0} for k, label, note in MOVE_GROUPS}
    for m in moves:
        g = groups[key(m[0])]
        g["rows"].append(m)
        g["total"] += m[1]
    return [g for g in groups.values() if g["rows"]]


def _group_assets(wallet, cash, orders, cut, pool, n_projects, stock_lines, held, held_value, lp_units, lp_left) -> list:
    """Section 1 by category: liquid ISK, reward ISK in projects, stock listed for sale, physical items in stock
    (the inputs bought to convert), goods held from projects, loyalty points. Each with its items behind a click."""
    groups = []
    rows = [["Master wallet, division 1", wallet, "Balance from the corporation's journal"]]
    for d in sorted(k for k in cash if k != 1):
        if abs(cash[d]) >= 1:
            rows.append([f"Wallet division {d}", cash[d], "Balance from the corporation's journal"])
    for o in orders:
        if o["is_buy"] and o["issued"] <= cut and o["escrow"]:
            rows.append([f"Escrow of the buy order for {o['name']}", o["escrow"], f"{o['remain']:,} left to buy at {o['price']:,.2f}"])
    groups.append({"key": "cash", "label": "Liquid ISK", "id": "as-cash", "rows": rows, "total": sum(r[1] for r in rows)})
    groups.append({"key": "pool", "label": "Reward ISK in active corporation projects", "id": "as-pool", "total": pool,
                   "rows": [[f"{n_projects} active projects", pool, "Rewards not yet paid out, read from EVE"]]})
    listed, physical = [], []
    for s in stock_lines:
        if s["units"] < 0.5:
            continue
        where = f" at {s['location'].split(' - ')[0]}" if s["location"] else ""
        row = [f"{s['name']}, {s['units']:,.0f} units", s["value"],
               f"At cost, {s['unit_cost']:,.0f} ISK a unit" + (f"; listed at {s['list_price']:g}{where}" if s["list_price"] else "") + (f"; {s['sold']:,.0f} sold since the baseline" if s["sold"] else "")]
        (listed if (s["list_price"] or s["sold"]) else physical).append(row)
    if listed:
        groups.append({"key": "listed", "label": "Stock listed for sale", "id": "as-listed", "rows": listed, "total": sum(r[1] for r in listed)})
    if physical:
        groups.append({"key": "physical", "label": "Physical items in stock", "id": "as-physical", "rows": physical, "total": sum(r[1] for r in physical),
                       "note": "Inputs bought to convert in the LP store, and other items held for use, at cost"})
    held_rows = [[name, cost, "At what the projects paid"] for name, cost in sorted(held.items(), key=lambda kv: -kv[1]) if cost >= 0.05e6]
    if held_rows:
        groups.append({"key": "held", "label": "Goods held from project buybacks", "id": "as-held", "rows": held_rows, "total": sum(held.values()),
                       "note": f"At what the projects paid for them; {held_value / M:,.1f} M at Jita's highest buy"})
    if lp_left:
        groups.append({"key": "lp", "label": "Loyalty points", "id": "as-lp", "total": lp_left,
                       "rows": [[f"{lp_units:,} LP not converted yet", lp_left, "At what the corporation paid per LP"]]})
    return groups


def open_period(start_at, source: str = "", note: str = ""):
    """Open a reporting period at `start_at`: the corporation's position at that moment becomes the opening.
    Returns the new row, or None when a period already starts at or after that moment."""
    first = budget()
    if first is None or start_at <= first.taken_at:
        return None
    if BooksBaseline.objects.filter(taken_at__gte=start_at).exists():
        return None
    d = compute(now=start_at)
    return BooksBaseline.objects.create(
        taken_at=start_at, loan=first.loan, wallet=d["wallet"], other_divs=d["other_divs"], pool=d["pool"], held=d["held_total"],
        open_escrow=d["open_escrow"], lp_units=int(d["lp_units"]), lp_cost=d["lp_cost"], opening_result=d["result"], source=source[:200], note=note[:300],
    )


def state_posts() -> list:
    """The State of the Alliance posts on the alliance site, newest first: [(date, title, slug)]. posts.json
    first, the front page's links as the fallback; [] when the site does not answer."""
    import datetime as dt
    import requests

    url = app_settings.SHIPYARD_BOOKS_POSTS_URL.rstrip("/") + "/"
    pattern = re.compile(app_settings.SHIPYARD_BOOKS_POST_PATTERN, re.I)
    out = []
    try:
        r = requests.get(url + "posts.json", timeout=20)
        if r.ok:
            for p in r.json():
                if pattern.search(p.get("slug", "")) or pattern.search(p.get("title", "").lower().replace(" ", "-")):
                    out.append((dt.date.fromisoformat(p["date"]), p.get("title", ""), p.get("slug", "")))
        else:
            r = requests.get(url, timeout=20)
            for slug in re.findall(r'href="/?([0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+)\.html"', r.text if r.ok else ""):
                if pattern.search(slug):
                    out.append((dt.date.fromisoformat(slug[:10]), slug[11:].replace("-", " ").capitalize(), slug))
    except Exception:  # noqa: BLE001
        return []
    out.sort(reverse=True)
    return out


def check_posts():
    """Open a new period when the alliance site has a State of the Alliance post newer than the current one.
    Returns the new period or None."""
    import datetime as dt
    posts = state_posts()
    if not posts:
        return None
    day, title, slug = posts[0]
    start = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)
    current = baseline()
    if current is None or start <= current.taken_at:
        return None
    return open_period(start, source=f"{title} ({day.isoformat()})", note=f"opened by the hourly check from {app_settings.SHIPYARD_BOOKS_POSTS_URL}{slug}.html")


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
