"""The Corp projects tab's history: what projects paid members, what the corp sold, and the two matched.

Everything is turned into small timestamped events here; the page's JavaScript buckets them into
days, weeks or a custom number of days and draws the graphs (static/shipyard/projects_charts.js),
so changing the interval needs no reload (owner's request 2026-10-18).

- Payouts: each member's contribution growing between two hourly reads, times the project's reward
  per unit (ProjectContribution). The first read (2026-10-14) found contributions made before the
  reads began; those are spread evenly over the days between the project's start and that read and
  marked as estimated.
- Funding: the corp wallet journal's project_payouts entries; a negative amount is ISK put into a
  project, a positive one the rest of a pool refunded when the project closed.
- Sales: the corp's market transactions (sells) of anything the projects bought, or of what that
  reprocesses into.
- Matching (first in, first out): every delivery becomes a lot. A type the corp sells as delivered
  (Zero-Point Condensate) stays a lot of itself; an ore or ice the corp never sold as delivered is
  turned into its reprocessing outputs at the Shipyard's yield, the cost split over the outputs by
  their Jita buy value. Each sale then takes the oldest lots of its type that existed by then; what
  a sale cannot match is "other sales" (stock that did not come from projects). What no sale took is
  stock on hand.
"""

import datetime as dt
import math
from collections import defaultdict, deque

from ..models import CorpJournalEntry, CorpProject, CorpWalletTransaction, MarketLocation, MaterialType, Ore, PriceSnapshot
from . import projects, reprocessing

ESTIMATE_GAP = dt.timedelta(hours=6)  # a first read this long after the project started holds a backlog
KIND_OTHER = "item"
KIND_SCAN = "scan"
KIND_LABELS = {"ore": "Asteroid ore", "moon": "Moon ore", "ice": "Ice", "abyssal": "Abyssal ore", KIND_OTHER: "Other items", KIND_SCAN: "Scanning"}


def _iso(when):
    return when.isoformat(timespec="minutes")


def _market():
    return MarketLocation.objects.filter(is_active=True).order_by("-is_default", "name").first()


def delivered_type(project):
    """The item type a deliver-item project buys, or None (scanning, manual, ...)."""
    for item in (project.details or {}).get("configuration") or []:
        if isinstance(item, dict):
            for key, value in item.items():
                if key == "deliver_item":
                    for it in (value or {}).get("items") or []:
                        if it.get("type_id"):
                            return int(it["type_id"])
    cfg = (project.details or {}).get("configuration")
    if isinstance(cfg, dict) and "deliver_item" in cfg:
        for it in (cfg["deliver_item"] or {}).get("items") or []:
            if it.get("type_id"):
                return int(it["type_id"])
    return None


def _spread(start, end):
    """Split a backlog evenly over the days between start and end: [(when, share)], midday of each day."""
    days = max(1, math.ceil((end - start).total_seconds() / 86400))
    step = (end - start) / days
    return [(start + step * (i + 0.5), 1.0 / days) for i in range(days)]


def payout_events(cid=None) -> list[dict]:
    """Member payouts: [{t, project, type_id, kind, member, units, isk, est}] oldest first."""
    cid = cid or projects.corp_id()
    out = []
    for p in CorpProject.objects.filter(corporation_id=cid).prefetch_related("contributions", "snapshots"):
        rate = p.reward_per_contribution or 0
        if not rate:
            continue
        type_id = delivered_type(p)
        first_read = min((s.taken_at for s in p.snapshots.all()), default=None)
        prev = {}
        for c in sorted(p.contributions.all(), key=lambda r: (r.character_id, r.taken_at)):
            first_row = c.character_id not in prev
            delta = c.contributed - prev.get(c.character_id, 0)
            prev[c.character_id] = c.contributed
            if delta <= 0:
                continue
            base = {"project": p.name, "pid": p.project_id, "type_id": type_id, "member": c.character_id, "name": c.character_name}
            # a member's first row at the project's first read, long after the project started: work done before we watched
            backlog = (first_row and first_read is not None and p.created is not None
                       and abs((c.taken_at - first_read).total_seconds()) < 7200 and c.taken_at - p.created > ESTIMATE_GAP)
            if backlog:
                for when, share in _spread(p.created, c.taken_at):
                    out.append({**base, "t": when, "units": delta * share, "isk": delta * share * rate, "est": True})
            else:
                out.append({**base, "t": c.taken_at, "units": float(delta), "isk": delta * rate, "est": False})
    out.sort(key=lambda e: e["t"])
    return out


def funding_events(cid=None) -> list[dict]:
    """[{t, amount}] from the journal: negative = put into a project, positive = refund on closing."""
    cid = cid or projects.corp_id()
    qs = CorpJournalEntry.objects.filter(corporation_id=cid, ref_type="project_payouts").order_by("date")
    return [{"t": e.date, "amount": e.amount} for e in qs]


def _prices(type_ids, market):
    if market is None:
        return {}
    return {p.type_id: (p.buy_max or 0.0) for p in PriceSnapshot.objects.filter(type_id__in=list(type_ids), location=market)}


def _names(type_ids):
    names = {o.type_id: o.name for o in Ore.objects.filter(type_id__in=list(type_ids))}
    names.update({m.type_id: m.name for m in MaterialType.objects.filter(type_id__in=list(type_ids)) if m.type_id not in names})
    return names


def ledger(cid=None, until=None) -> dict:
    """The deliveries turned into lots and matched against the corp's sales, first in first out.
    until = a cut-off time: payouts and sales after it are left out (the balance sheet's moment).
    Returns the working pieces: lots (type_id -> deque of [t, qty, unit_cost] still unsold), matches,
    others, stock, payout_rows, prices (Jita buy), names, market, sells."""
    cid = cid or projects.corp_id()
    market = _market()
    pays = payout_events(cid)
    if until is not None:
        pays = [e for e in pays if e["t"] <= until]
    project_types = {e["type_id"] for e in pays if e["type_id"]}
    ores = {o.type_id: o for o in Ore.objects.filter(type_id__in=list(project_types))}
    outputs = {int(m) for o in ores.values() for m in (o.materials or {})}
    sells_qs = CorpWalletTransaction.objects.filter(corporation_id=cid, is_buy=False)
    if until is not None:
        sells_qs = sells_qs.filter(date__lte=until)
    sells = list(sells_qs.order_by("date"))
    sold_types = {t.type_id for t in sells}
    universe = project_types | outputs
    prices = _prices(universe, market)
    names = _names(universe | sold_types)
    yields = {tid: reprocessing.yield_for(o) for tid, o in ores.items()}

    def reproc_value(tid, units):
        o = ores.get(tid)
        if not o:
            return 0.0
        batches = units / float(o.portion_size or 1)
        return sum(batches * float(q) * yields[tid] * prices.get(int(m), 0.0) for m, q in (o.materials or {}).items())

    # --- lots from deliveries
    lots = defaultdict(deque)  # type_id -> deque of [t, qty, unit_cost]
    stock = []  # [t, +/- cost]
    payout_rows = []
    for e in pays:
        tid = e["type_id"]
        o = ores.get(tid)
        kind = (o.kind if o else (KIND_OTHER if tid else KIND_SCAN))
        m3 = e["units"] * (o.volume if o else 0.0)
        asis = e["units"] * prices.get(tid, 0.0) if tid else 0.0
        reproc = reproc_value(tid, e["units"]) if o else asis
        payout_rows.append([_iso(e["t"]), kind, e["project"], e["member"], round(e["units"], 3), round(e["isk"], 2),
                            round(m3, 2), 1 if e["est"] else 0, round(asis, 2), round(reproc, 2), names.get(tid, e["project"])])
        if not tid or e["isk"] <= 0:
            continue
        if o is None or tid in sold_types:
            lots[tid].append([e["t"], e["units"], e["isk"] / e["units"] if e["units"] else 0.0])
        else:
            batches = e["units"] / float(o.portion_size or 1)
            parts = [(int(m), batches * float(q) * yields[tid]) for m, q in (o.materials or {}).items()]
            total = sum(q * prices.get(m, 0.0) for m, q in parts) or 1.0
            for m, q in parts:
                if q > 0:
                    share = (q * prices.get(m, 0.0)) / total
                    lots[m].append([e["t"], q, e["isk"] * share / q])
        stock.append([_iso(e["t"]), round(e["isk"], 2)])

    # --- sales against the lots, first in first out, only lots that existed at the sale
    matches, others = [], []
    for s in sells:
        if s.type_id not in universe:
            continue
        need = float(s.quantity)
        queue = lots.get(s.type_id) or deque()
        revenue = cost = matched = 0.0
        while need > 1e-9 and queue and queue[0][0] <= s.date:
            lot = queue[0]
            take = min(need, lot[1])
            revenue += take * s.unit_price
            cost += take * lot[2]
            matched += take
            lot[1] -= take
            need -= take
            if lot[1] <= 1e-9:
                queue.popleft()
        if matched:
            matches.append([_iso(s.date), names.get(s.type_id, str(s.type_id)), round(revenue, 2), round(cost, 2), round(matched, 2)])
            stock.append([_iso(s.date), round(-cost, 2)])
        if need > 1e-9:
            others.append([_iso(s.date), names.get(s.type_id, str(s.type_id)), round(need * s.unit_price, 2)])
    stock.sort(key=lambda r: r[0])
    return {"lots": lots, "matches": matches, "others": others, "stock": stock, "payout_rows": payout_rows,
            "prices": prices, "names": names, "market": market, "sells": sells}


def books(cid=None) -> dict:
    """Everything the graphs need, as JSON-ready lists. Pure apart from the database reads."""
    cid = cid or projects.corp_id()
    led = ledger(cid)
    lots, prices = led["lots"], led["prices"]
    left_cost = sum(q * c for queue in lots.values() for _, q, c in queue)
    left_value = sum(q * prices.get(tid, 0.0) for tid, queue in lots.items() for _, q, _ in queue)
    payout_rows = led["payout_rows"]
    market = led["market"]
    return {
        "payouts": payout_rows,
        "funding": [[_iso(f["t"]), round(f["amount"], 2)] for f in funding_events(cid)],
        "matches": led["matches"],
        "others": led["others"],
        "stock": led["stock"],
        "stock_now": {"cost": round(left_cost, 2), "value": round(left_value, 2)},
        "kinds": KIND_LABELS,
        "first": payout_rows[0][0] if payout_rows else None,
        "market": market.name if market else "",
        "has_sales": bool(led["sells"]),
    }
