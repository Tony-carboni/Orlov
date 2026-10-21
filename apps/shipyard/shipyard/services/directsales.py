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


def quote(text: str, user) -> dict:
    """Price the pasted items by the rule and work out what the projects paid for them. Changes nothing."""
    settings = board.get_user_settings(user)
    market = settings.market
    cat = _catalog()
    parsed = parse_lines(text)
    ore_rows = {r.ore.type_id: r for r in reprocessing.dashboard_rows(market, settings)}
    led = projectbooks.ledger(projects.corp_id())
    lots, yields, led_ores = led["lots"], led["yields"], led["ores"]
    buy = _buy_prices([resolve(n, cat)[0] for n, _, _ in parsed if resolve(n, cat)], market)
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
        if ore is not None:
            row = ore_rows.get(tid)
            repro = row.net_value * ORE_SHARE if row else None
            cap = row.sell_price if row and row.sell_price else None
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
        lines.append({"type_id": tid, "name": full, "qty": qty, "unit": round(unit, 2), "basis": basis, "line": round(line, 2),
                      "cost": round(cost, 2), "held": round(taken, 3), "profit": round(line - cost, 2), "is_ore": ore is not None,
                      "short": taken + 1e-6 < qty if (o is None and ore is None) or (ore is not None and tid in lots) else False})
    return {"lines": lines, "problems": problems, "total": round(total, 2), "cost": round(cost_total, 2), "profit": round(total - cost_total, 2),
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
    led = projectbooks.ledger(projects.corp_id())
    now = timezone.now()
    lines, cost = [], 0.0
    for tid, queue in led["lots"].items():
        units = sum(r[1] for r in queue if r[0] <= now)
        if units <= 0:
            continue
        c = sum(r[1] * r[2] for r in queue if r[0] <= now)
        cost += c
        lines.append({"type_id": tid, "name": led["names"].get(tid, str(tid)), "qty": round(units, 3), "unit": 0.0, "basis": "written off",
                      "line": 0.0, "cost": round(c, 2), "held": round(units, 3), "profit": round(-c, 2), "is_ore": False, "short": False})
    code = "WO-" + now.strftime("%y%m%d") + "-" + "".join(random.choice(CODE_ALPHABET) for _ in range(2))
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
