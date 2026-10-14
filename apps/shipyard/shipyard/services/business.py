"""My business: the member's own wallet, ship sales and production (owner's request, 2026-10-14).

Three sources, one page:
- **Wallet and sales** come from Member Audit's copy of the chosen character's wallet (balance,
  journal, market transactions; Member Audit refreshes them about hourly). Nothing is read from
  ESI here, the character only has to be registered in Member Audit (the front door does that).
- **Production** comes from the production corp's industry jobs: the owner's jobs run in the
  name of Orlov Arms International, so the character's own job list is empty. An hourly task
  copies the corp's jobs (ESI, `include_completed`, the last 90 days) into `CorpIndustryJob`
  and keeps them, through a token with `esi-industry.read_corporation_jobs.v1` from a character
  of the corp with the Factory Manager role (the CEO has it). The page offers the SSO button
  when no such token exists.
- Ships are grouped the way the dashboard does: the category (Base, Navy, Pirate, ...) and the
  hull class (Frigate, Destroyer, ...). Fuel blocks are counted apart from ships.
"""

import datetime as dt
import logging
from collections import defaultdict

from allianceauth.eveonline.models import EveCharacter
from django.utils import timezone
from esi.models import Token

from .. import app_settings, constants
from ..models import CorpIndustryJob, Ship
from .http import polite_pause, session
from .wallet import period_key

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"
PERIODS = ("day", "week", "month")
MANUFACTURING = 1
HULL_ORDER = list(constants.HULL_ORDER) + ["Fuel block"]
CATEGORY_ORDER = list(constants.CATEGORY_ORDER) + [constants.CAT_FUEL]
ACTIVE_STATUSES = {"active", "paused", "ready"}


# --- the member's character in Member Audit ------------------------------------------------

def ma_character(character_id):
    """Member Audit's record of this character, or None when it is not registered there."""
    if not character_id:
        return None
    try:
        from memberaudit.models import Character

        return Character.objects.select_related("eve_character").filter(eve_character__character_id=int(character_id)).first()
    except Exception as exc:  # noqa: BLE001
        logger.info("Member Audit not available: %s", exc)
        return None


def ma_freshness(character) -> dict:
    """When Member Audit last read the wallet sections, by section."""
    out = {}
    if character is None:
        return out
    try:
        from memberaudit.models import CharacterUpdateStatus

        for s in CharacterUpdateStatus.objects.filter(character=character, section__in=["wallet_balance", "wallet_journal", "wallet_transactions"]):
            out[s.section] = {"ok": s.is_success, "at": getattr(s, "run_finished_at", None) or getattr(s, "update_finished_at", None)}
    except Exception as exc:  # noqa: BLE001
        logger.info("Member Audit update status not read: %s", exc)
    return out


# --- catalog -------------------------------------------------------------------------------

def catalog() -> dict:
    """{type_id: {name, category, hull, units_per_run}} for every ship and fuel block we know."""
    return {
        s.type_id: {"name": s.name, "category": s.category, "hull": s.hull_size, "units_per_run": s.units_per_run or 1}
        for s in Ship.objects.all()
    }


# --- wallet --------------------------------------------------------------------------------

def wallet_balance(character):
    try:
        return float(character.wallet_balance.total)
    except Exception:  # noqa: BLE001
        return None


def journal_rows(character, since=None) -> list[dict]:
    """The character's journal entries from Member Audit as plain dicts."""
    from memberaudit.models import CharacterWalletJournalEntry

    qs = CharacterWalletJournalEntry.objects.filter(character=character)
    if since is not None:
        qs = qs.filter(date__gte=since)
    return [{"date": e.date, "ref_type": e.ref_type, "amount": float(e.amount)} for e in qs.only("date", "ref_type", "amount")]


def wallet_summary(rows: list[dict], period: str) -> dict:
    """Totals and a per-period series of money in and out, plus the journal by type. Pure."""
    income = sum(r["amount"] for r in rows if r["amount"] > 0)
    expenses = sum(r["amount"] for r in rows if r["amount"] < 0)
    by_type = defaultdict(lambda: {"count": 0, "total": 0.0})
    series = defaultdict(lambda: {"in": 0.0, "out": 0.0})
    for r in rows:
        by_type[r["ref_type"]]["count"] += 1
        by_type[r["ref_type"]]["total"] += r["amount"]
        key = period_key(r["date"], period)
        if r["amount"] > 0:
            series[key]["in"] += r["amount"]
        else:
            series[key]["out"] += r["amount"]
    types = sorted(((t, v["count"], v["total"]) for t, v in by_type.items()), key=lambda x: -abs(x[2]))
    columns = sorted(series)
    market = {
        "sales": sum(r["amount"] for r in rows if r["ref_type"] == "market_transaction" and r["amount"] > 0),
        "purchases": sum(r["amount"] for r in rows if r["ref_type"] in ("market_transaction", "market_escrow") and r["amount"] < 0),
        "fees": sum(r["amount"] for r in rows if r["ref_type"] in ("brokers_fee", "transaction_tax")),
    }
    return {
        "income": income, "expenses": expenses, "net": income + expenses, "count": len(rows),
        "types": types, "columns": columns,
        "series": [{"key": k, "in": series[k]["in"], "out": series[k]["out"], "net": series[k]["in"] + series[k]["out"]} for k in columns],
        "market": market,
    }


# --- ship sales ----------------------------------------------------------------------------

def sales_rows(character, since=None) -> list[dict]:
    """Every sale of a catalog ship or fuel block by this character, from Member Audit's transactions."""
    from memberaudit.models import CharacterWalletTransaction

    cat = catalog()
    qs = CharacterWalletTransaction.objects.filter(character=character, is_buy=False, eve_type_id__in=list(cat))
    if since is not None:
        qs = qs.filter(date__gte=since)
    out = []
    for t in qs.only("date", "eve_type_id", "quantity", "unit_price"):
        c = cat[t.eve_type_id]
        out.append({
            "date": t.date, "type_id": t.eve_type_id, "name": c["name"], "category": c["category"], "hull": c["hull"],
            "quantity": int(t.quantity), "unit_price": float(t.unit_price), "total": int(t.quantity) * float(t.unit_price),
        })
    return out


def _order(values, order):
    known = [v for v in order if v in values]
    return known + sorted(v for v in values if v not in order)


def pivot(rows: list[dict], period: str, group: str, value: str) -> dict:
    """{columns (oldest first), rows [(label, {column: value}, total)], totals {column: value}}. Pure."""
    cells = defaultdict(lambda: defaultdict(float))
    totals = defaultdict(float)
    for r in rows:
        key = period_key(r["date"], period)
        cells[r[group]][key] += r[value]
        totals[key] += r[value]
    columns = sorted(totals)
    order = CATEGORY_ORDER if group == "category" else HULL_ORDER
    labels = _order(set(cells), order)
    return {
        "columns": columns,
        "rows": [(label, dict(cells[label]), sum(cells[label].values())) for label in labels],
        "totals": dict(totals),
    }


def by_type(rows: list[dict], count_key: str = "quantity", money_key: str = "total") -> list[dict]:
    """One line per product: units, ISK, average price, first and last date. Pure."""
    agg = {}
    for r in rows:
        a = agg.setdefault(r["type_id"], {"type_id": r["type_id"], "name": r["name"], "category": r["category"], "hull": r["hull"],
                                          "units": 0, "isk": 0.0, "lines": 0, "first": r["date"], "last": r["date"]})
        a["units"] += r[count_key]
        a["isk"] += r[money_key]
        a["lines"] += 1
        a["first"] = min(a["first"], r["date"])
        a["last"] = max(a["last"], r["date"])
    out = list(agg.values())
    for a in out:
        a["average"] = a["isk"] / a["units"] if a["units"] else 0.0
    return sorted(out, key=lambda a: -a["units"])


def split_fuel(rows: list[dict]) -> tuple:
    ships = [r for r in rows if r["category"] != constants.CAT_FUEL]
    fuel = [r for r in rows if r["category"] == constants.CAT_FUEL]
    return ships, fuel


def sales_summary(rows: list[dict], period: str) -> dict:
    ships, fuel = split_fuel(rows)
    return {
        "units": sum(r["quantity"] for r in ships), "isk": sum(r["total"] for r in ships), "lines": len(ships),
        "fuel_units": sum(r["quantity"] for r in fuel), "fuel_isk": sum(r["total"] for r in fuel),
        "by_category": pivot(ships, period, "category", "quantity"),
        "by_hull": pivot(ships, period, "hull", "quantity"),
        "isk_by_category": pivot(ships, period, "category", "total"),
        "types": by_type(ships),
        "fuel_types": by_type(fuel),
    }


# --- production: the corp's industry jobs ----------------------------------------------------

def corp_id() -> int:
    return int(app_settings.SHIPYARD_PRODUCTION_CORP_ID)


def scopes() -> list[str]:
    return list(app_settings.SHIPYARD_PRODUCTION_SCOPES)


def token():
    """A valid token with the corp jobs scope for a character of the production corp, or None."""
    ids = list(EveCharacter.objects.filter(corporation_id=corp_id()).values_list("character_id", flat=True))
    if not ids:
        return None
    return Token.objects.filter(character_id__in=ids).require_scopes(scopes()).require_valid().order_by("-created").first()


def _parse_dt(value):
    if not value:
        return None
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _jobs_pages(access_token: str, max_pages: int = 20) -> list[dict]:
    path = f"{ESI}/corporations/{corp_id()}/industry/jobs/"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    first = session().get(path, params={"include_completed": "true", "page": 1}, headers=headers, timeout=30)
    first.raise_for_status()
    rows = list(first.json() or [])
    pages = min(int(first.headers.get("X-Pages") or 1), max_pages)
    for page in range(2, pages + 1):
        polite_pause()
        r = session().get(path, params={"include_completed": "true", "page": page}, headers=headers, timeout=30)
        r.raise_for_status()
        rows.extend(r.json() or [])
    return rows


def refresh() -> dict:
    """Copy every job ESI reports (the last 90 days, running and completed) into CorpIndustryJob; keep older ones."""
    tok = token()
    if tok is None:
        raise RuntimeError("no token with the corporation jobs scope for a character of the production corp")
    rows = _jobs_pages(tok.valid_access_token())
    cid = corp_id()
    now = timezone.now()
    added = updated = 0
    for j in rows:
        _, created = CorpIndustryJob.objects.update_or_create(
            job_id=int(j["job_id"]),
            defaults={
                "corporation_id": cid,
                "installer_id": int(j.get("installer_id") or 0),
                "activity_id": int(j.get("activity_id") or 0),
                "blueprint_type_id": int(j.get("blueprint_type_id") or 0),
                "product_type_id": int(j["product_type_id"]) if j.get("product_type_id") else None,
                "runs": int(j.get("runs") or 0),
                "status": str(j.get("status") or ""),
                "start_date": _parse_dt(j.get("start_date")),
                "end_date": _parse_dt(j.get("end_date")),
                "completed_date": _parse_dt(j.get("completed_date")),
                "location_id": int(j.get("facility_id") or j.get("location_id") or 0),
                "cost": float(j.get("cost") or 0),
                "fetched_at": now,
            },
        )
        if created:
            added += 1
        else:
            updated += 1
    resolve_installers()
    return {"added": added, "updated": updated, "total": CorpIndustryJob.objects.filter(corporation_id=cid).count()}


def resolve_installers() -> int:
    todo = list(CorpIndustryJob.objects.filter(installer_name="").values_list("installer_id", flat=True).distinct())
    todo = [i for i in todo if i]
    if not todo:
        return 0
    names = {}
    try:
        from eveuniverse.models import EveEntity

        resolver = EveEntity.objects.bulk_resolve_names(todo)
        names = {i: resolver.to_name(i) or "" for i in todo}
    except Exception as exc:  # noqa: BLE001
        logger.info("installer names not resolved: %s", exc)
    n = 0
    for i, name in names.items():
        if name:
            n += CorpIndustryJob.objects.filter(installer_id=i, installer_name="").update(installer_name=name)
    return n


def production_rows(installer_id=None, since=None) -> list[dict]:
    """Manufacturing jobs of the production corp for catalog products, as plain dicts (one per job)."""
    cat = catalog()
    qs = CorpIndustryJob.objects.filter(corporation_id=corp_id(), activity_id=MANUFACTURING, product_type_id__in=list(cat))
    if installer_id:
        qs = qs.filter(installer_id=int(installer_id))
    if since is not None:
        qs = qs.filter(start_date__gte=since)
    out = []
    for j in qs:
        c = cat[j.product_type_id]
        out.append({
            "job_id": j.job_id, "date": j.start_date, "end": j.end_date, "status": j.status,
            "type_id": j.product_type_id, "name": c["name"], "category": c["category"], "hull": c["hull"],
            "runs": j.runs, "quantity": j.runs * c["units_per_run"], "total": j.cost, "installer": j.installer_name or str(j.installer_id),
        })
    return out


def production_summary(rows: list[dict], period: str, now=None) -> dict:
    now = now or timezone.now()
    ships, fuel = split_fuel(rows)
    status = defaultdict(int)
    for r in rows:
        status[r["status"]] += 1
    first = min((r["date"] for r in rows if r["date"]), default=None)
    weeks = max((now - first).total_seconds() / (7 * 86400), 1.0) if first else 1.0
    return {
        "jobs": len(rows), "units": sum(r["quantity"] for r in ships), "cost": sum(r["total"] for r in rows),
        "fuel_units": sum(r["quantity"] for r in fuel),
        "active": sum(1 for r in rows if r["status"] in ACTIVE_STATUSES),
        "status": dict(status),
        "per_week": {"jobs": len(rows) / weeks, "units": sum(r["quantity"] for r in ships) / weeks},
        "by_category": pivot(ships, period, "category", "quantity"),
        "by_hull": pivot(ships, period, "hull", "quantity"),
        "types": by_type(ships, count_key="quantity", money_key="total"),
        "fuel_types": by_type(fuel, count_key="quantity", money_key="total"),
    }


def compare(sales: dict, production: dict) -> list[dict]:
    """Per category: units produced and sold in the range, and the difference. Pure."""
    produced = {label: total for label, _, total in production["by_category"]["rows"]}
    sold = {label: total for label, _, total in sales["by_category"]["rows"]}
    out = []
    for label in _order(set(produced) | set(sold), CATEGORY_ORDER):
        out.append({"category": label, "produced": produced.get(label, 0), "sold": sold.get(label, 0),
                    "difference": produced.get(label, 0) - sold.get(label, 0)})
    return out


# --- charts --------------------------------------------------------------------------------

def chart(pivot_data: dict, label_order=None) -> dict:
    """Chart.js data for a stacked bar chart: labels = periods oldest first, one dataset per row."""
    return {
        "labels": list(pivot_data["columns"]),
        "datasets": [{"label": label, "data": [round(cells.get(c, 0), 2) for c in pivot_data["columns"]]} for label, cells, _ in pivot_data["rows"]],
    }


def wallet_chart(summary: dict) -> dict:
    return {
        "labels": [s["key"] for s in summary["series"]],
        "datasets": [
            {"label": "In", "data": [round(s["in"], 2) for s in summary["series"]]},
            {"label": "Out", "data": [round(s["out"], 2) for s in summary["series"]]},
            {"label": "Net", "data": [round(s["net"], 2) for s in summary["series"]], "type": "line"},
        ],
    }
