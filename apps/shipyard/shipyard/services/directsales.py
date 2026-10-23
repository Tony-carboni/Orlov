"""Register a direct sale of project goods on the Finance tab (owner's design, 2026-10-21).

The owner pastes the items he is about to sell (one per line, as the game copies them: name, a tab,
the quantity), the page quotes them by the owner's rule, and registers the sale under a short code
(DS-XXXX). The buyer's ISK is then deposited into a corp wallet with that code in the reason, and the
books take the registered lots out of the goods held when the deposit appears (services/books.py).

The rule: compressed ore and ice at 95 % of the Reprocessing tab's value (the owner's own setup), never
above Jita's lowest sell (owner's correction of 2026-10-21); everything else at Jita's highest buy. Net profit = the quote minus what the
projects paid for those goods (first in, first out, an ore through its minerals as the ledger holds them).
EVE's transfer reason holds 40 characters, which is why the code and not the item list goes in it.
"""

import random
import re
from collections import deque

from django.utils import timezone

from ..models import BookDirectSale, LpTypeMarket, MaterialType, Ore, PriceSnapshot
from . import board, fuzzwork, projectbooks, projects, reprocessing

ORE_SHARE = 0.95
CODE_RE = re.compile(r"\bDS-([A-HJ-NP-Z2-9]{4,6})\b", re.I)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L
LINE_TAB = re.compile(r"^(.*?)[\t,;]+\s*([\d.,]+)\s*$")
LINE_LEAD = re.compile(r"^([\d.,]+)\s*[x×]?\s+(.+?)\s*$")
LINE_TRAIL = re.compile(r"^(.+?)\s+[x×]?\s*([\d.,]+)\s*$")


def _int(s: str) -> int:
    return int(re.sub(r"[.,]", "", s))


def parse_lines(text: str) -> list:
    """[(name, qty, raw)] from the pasted text, one item per line. 'Name<TAB>303', '303 Name', 'Name 303', 'Name x303'."""
    out = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = LINE_TAB.match(line) or LINE_LEAD.match(line)
        if m and m.re is LINE_LEAD:
            out.append((m.group(2).strip(), _int(m.group(1)), raw))
            continue
        if m is None:
            m = LINE_TRAIL.match(line)
        if m:
            out.append((m.group(1).strip(), _int(m.group(2)), raw))
        else:
            out.append((line, None, raw))
    return out


def _catalog() -> dict:
    """lower-cased name -> (type_id, name, Ore or None) for everything the Shipyard knows by name."""
    cat = {}
    for m in LpTypeMarket.objects.all():
        cat[m.name.lower()] = (m.type_id, m.name, None)
    for m in MaterialType.objects.all():
        cat[m.name.lower()] = (m.type_id, m.name, None)
    for o in Ore.objects.all():
        cat[o.name.lower()] = (o.type_id, o.name, o)
    return cat


def resolve(name: str, cat: dict):
    key = name.lower()
    if key in cat:
        return cat[key]
    hits = [k for k in cat if k.startswith(key)] or [k for k in cat if key in k]
    return cat[min(hits, key=len)] if hits else None


def _buy_prices(type_ids, market) -> dict:
    """Jita highest buy per type: the price table, then the LP store's table, then Fuzzwork for the rest."""
    ids = {int(t) for t in type_ids}
    out = {}
    if market is not None:
        for p in PriceSnapshot.objects.filter(location=market, type_id__in=list(ids)):
            v = p.buy_max_near or p.buy_max
            if v:
                out[p.type_id] = float(v)
    for m in LpTypeMarket.objects.filter(type_id__in=[t for t in ids if t not in out]):
        if m.buy_max:
            out[m.type_id] = float(m.buy_max)
    missing = [t for t in ids if t not in out]
    if missing:
        try:
            station = int(market.station_id) if market is not None else 60003760
            for tid, a in fuzzwork.station_aggregates(station, missing).items():
                if a.get("buy_max"):
                    out[tid] = float(a["buy_max"])
        except Exception:  # noqa: BLE001
            pass
    return out


def _sell_prices(type_ids, market) -> dict:
    """Jita lowest sell per type: the price table, then the LP store's table, then Fuzzwork for the rest."""
    ids = {int(t) for t in type_ids}
    out = {}
    if market is not None:
        for p in PriceSnapshot.objects.filter(location=market, type_id__in=list(ids)):
            if p.sell_min:
                out[p.type_id] = float(p.sell_min)
    for m in LpTypeMarket.objects.filter(type_id__in=[t for t in ids if t not in out]):
        if m.sell_min:
            out[m.type_id] = float(m.sell_min)
    missing = [t for t in ids if t not in out]
    if missing:
        try:
            station = int(market.station_id) if market is not None else 60003760
            for tid, a in fuzzwork.station_aggregates(station, missing).items():
                if a.get("sell_min"):
                    out[tid] = float(a["sell_min"])
        except Exception:  # noqa: BLE001
            pass
    return out


# Sanity checks on the Jita prices behind a quote (owner, 2026-10-23): a line gets a flag when
SPREAD_FLAG = 0.20       # the gap between Jita sell and buy is more than this share of sell (thin or odd market)
UNDER_BUY_FLAG = 0.85    # the quote is below this share of Jita buy (the buyer could get more from Jita's buy orders)
REPRO_OVER_SELL_FLAG = 1.25  # the reprocessing value is above this multiple of Jita sell (minerals or the sell price look off)


def flags(unit, buy, sell, repro) -> list:
    """Why a line's prices deserve a second look. Pure; empty when nothing is odd."""
    out = []
    if not buy:
        out.append("no Jita buy order")
    if not sell:
        out.append("no Jita sell order")
    if buy and sell and buy > sell:
        out.append(f"Jita buy {buy:,.2f} above sell {sell:,.2f}")
    elif buy and sell and (sell - buy) / sell > SPREAD_FLAG:
        out.append(f"Jita spread {(sell - buy) / sell:.0%} (sell {sell:,.2f}, buy {buy:,.2f})")
    if buy and unit < buy * UNDER_BUY_FLAG:
        out.append(f"quote {1 - unit / buy:.0%} under Jita buy")
    if sell and unit > sell * 1.0001:
        out.append("quote above Jita sell")
    if repro and sell and repro > sell * REPRO_OVER_SELL_FLAG:
        out.append(f"reprocessing value {repro / sell:.2f}x Jita sell")
    return out


def _pct(total, cost):
    return (total - cost) / cost if cost else None


def valuations(lines: list) -> list:
    """The six ways to value the pasted list, each with its margin against the projects' cost (owner, 2026-10-23).
    Pure. A line carries unit (the quote), buy, sell, repro (95 % of the reprocessing value, ores only), qty, cost."""
    cost = sum(ln["cost"] for ln in lines)

    def total(key):
        return sum(key(ln) * ln["qty"] for ln in lines)

    def ore_or_buy(ln, ore_value):
        return ore_value(ln) if ln["is_ore"] and ln.get("repro") is not None else (ln.get("buy") or ln["unit"])

    rows = [
        ("Direct-sale quote (the rule)", total(lambda ln: ln["unit"])),
        ("Paid via projects, first in first out", cost),
        ("Jita buy on everything", total(lambda ln: ln.get("buy") or 0)),
        ("Jita sell on everything", total(lambda ln: ln.get("sell") or 0)),
        ("95 % reprocessing on ores and ice, Jita buy on the rest, no cap", total(lambda ln: ore_or_buy(ln, lambda l: l["repro"]))),
        ("95 % reprocessing capped at Jita sell, Jita buy on the rest", total(lambda ln: ore_or_buy(ln, lambda l: min(l["repro"], l["sell"]) if l.get("sell") else l["repro"]))),
    ]
    return [{"label": label, "total": round(v, 2), "margin": round(v - cost, 2), "pct": _pct(v, cost), "is_cost": label.startswith("Paid")} for label, v in rows]


def quote(text: str, user) -> dict:
    """Price the pasted items by the rule and work out what the projects paid for them. Changes nothing."""
    settings = board.get_user_settings(user)
    market = settings.market
    cat = _catalog()
    parsed = parse_lines(text)
    ore_rows = {r.ore.type_id: r for r in reprocessing.dashboard_rows(market, settings)}
    led = projectbooks.ledger(projects.corp_id())
    lots, yields, led_ores = led["lots"], led["yields"], led["ores"]
    wanted = [resolve(n, cat)[0] for n, _, _ in parsed if resolve(n, cat)]
    buy = _buy_prices(wanted, market)
    sells = _sell_prices([t for t in wanted if t not in ore_rows], market)
    now = timezone.now()
    lines, problems, total, cost_total = [], [], 0.0, 0.0
    for name, qty, raw in parsed:
        hit = resolve(name, cat)
        if hit is None:
            problems.append(f"'{raw.strip()}': EVE item not recognised")
            continue
        if qty is None:
            problems.append(f"'{raw.strip()}': no quantity")
            continue
        tid, full, ore = hit
        b = buy.get(tid)
        repro = None
        if ore is not None:
            row = ore_rows.get(tid)
            repro = row.net_value * ORE_SHARE if row else None
            cap = row.sell_price if row and row.sell_price else None
            if b is None and row and row.buy_price:
                b = float(row.buy_price)
            if repro is None and cap is None:
                problems.append(f"{full}: no reprocessing value and no Jita sell")
                continue
            unit = min(v for v in (repro, cap) if v is not None)
            basis = (f"95 % of the reprocessing value {row.net_value:,.2f}" if row else "no reprocessing value") + (f", capped at Jita sell {cap:,.2f}" if cap is not None and (repro is None or cap < repro) else "")
        else:
            if b is None:
                problems.append(f"{full}: no Jita buy order known")
                continue
            unit, basis = b, f"Jita highest buy {b:,.2f}"
        # what the projects paid for these units, first in first out (ores through their minerals)
        cost = taken = 0.0
        o = ore if ore is not None and tid in led_ores else None
        if o is not None and tid not in lots:
            y = yields.get(tid) or reprocessing.yield_for(o)
            batches = qty / float(o.portion_size or 1)
            for m, q in (o.materials or {}).items():
                c, t = _take(lots[int(m)], batches * float(q) * y, now)
                cost += c
            taken = qty
        else:
            cost, taken = _take(lots[tid], float(qty), now)
        line = unit * qty
        total += line
        cost_total += cost
        s = float(row.sell_price) if ore is not None and row and row.sell_price else sells.get(tid)
        lines.append({"type_id": tid, "name": full, "qty": qty, "unit": round(unit, 2), "basis": basis, "line": round(line, 2),
                      "cost": round(cost, 2), "held": round(taken, 3), "profit": round(line - cost, 2), "is_ore": ore is not None,
                      "short": taken + 1e-6 < qty if (o is None and ore is None) or (ore is not None and tid in lots) else False,
                      "buy": round(b, 2) if b else None, "sell": round(s, 2) if s else None, "repro": round(repro, 2) if repro else None,
                      "flags": flags(unit, b, s, repro), "pct": _pct(line, cost)})
    vals = valuations(lines)
    return {"lines": lines, "problems": problems, "total": round(total, 2), "cost": round(cost_total, 2), "profit": round(total - cost_total, 2),
            "pct": _pct(total, cost_total), "valuations": vals, "flagged": sum(1 for ln in lines if ln["flags"]),
            "market": market.name if market else "", "rule": f"ore and ice at {ORE_SHARE:.0%} of the reprocessing value, never above Jita sell; other items at Jita buy"}


def _take(queue, need, until):
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


def new_code() -> str:
    while True:
        code = "DS-" + "".join(random.choice(CODE_ALPHABET) for _ in range(4))
        if not BookDirectSale.objects.filter(code=code).exists():
            return code


def register(text: str, user) -> BookDirectSale:
    """Quote and record the sale; returns the row with its code. Raises ValueError when nothing can be priced."""
    q = quote(text, user)
    if not q["lines"]:
        raise ValueError("; ".join(q["problems"]) or "nothing to sell")
    items = ", ".join(f"{ln['qty']:,} {ln['name']}" for ln in q["lines"])
    return BookDirectSale.objects.create(
        corporation_id=projects.corp_id(), code=new_code(), items=items[:500], lines=q["lines"], quote=q["total"], cost=q["cost"],
        created_by=getattr(user, "username", "")[:150], note=("; ".join(q["problems"]))[:200],
    )


def write_off(user, note: str = "") -> BookDirectSale:
    """Stock take (owner, 2026-10-21): every project-goods lot held right now leaves the books at cost, with
    no cash movement, because it was sold earlier without a record. Kept as a BookDirectSale with a WO code,
    no deposit, matched at the moment of the write-off; later deliveries accrue again."""
    from . import books  # here, not at the top: books imports this module

    now = timezone.now()
    lines, cost = [], 0.0
    # the lots as the books see them now: after every registered sale, override and earlier stock take
    for tid, name, units, c in books.compute()["lots_left"]:
        if units <= 0:
            continue
        cost += c
        lines.append({"type_id": tid, "name": name, "qty": round(units, 3), "unit": 0.0, "basis": "written off",
                      "line": 0.0, "cost": round(c, 2), "held": round(units, 3), "profit": round(-c, 2), "is_ore": False, "short": False})
    code = "WO-" + now.strftime("%y%m%d") + random.choice(CODE_ALPHABET)  # 10 characters, the column's width
    return BookDirectSale.objects.create(
        corporation_id=projects.corp_id(), code=code, items=("stock take: " + ", ".join(f"{ln['qty']:,.0f} {ln['name']}" for ln in lines))[:500],
        lines=lines, quote=0.0, cost=cost, created_by=getattr(user, "username", "")[:150], matched_at=now, note=note[:200],
    )


def write_offs():
    return list(BookDirectSale.objects.filter(corporation_id=projects.corp_id(), code__startswith="WO-").order_by("-matched_at"))


def pending():
    return list(BookDirectSale.objects.filter(corporation_id=projects.corp_id(), entry_id__isnull=True).exclude(code="").order_by("-created_at"))


def recent(limit=10):
    return list(BookDirectSale.objects.filter(corporation_id=projects.corp_id(), entry_id__isnull=False).exclude(code="").order_by("-matched_at")[:limit])
