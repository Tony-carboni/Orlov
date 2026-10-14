"""Structure income: the structure corp's wallet journal, kept as our own ledger.

The Raitaru's facility tax, reprocessing tax, market broker fees and office rent land in
the wallet of the corporation that owns the structures (Gewoon voor structures, GWON).
ESI only serves the recent journal, so an hourly task copies every new entry into
`WalletJournalEntry` and the page works from our copy: full list, who pays, how much per
day, week, month or quarter (owner's request, 2026-10-14).

Token: any valid token with the corporation wallet scopes whose character is in the
structure corp and holds the Accountant or Junior Accountant role (the owner's alt
Vieze Jonge Pass, GWON's CEO). The page offers the SSO button when none exists.
"""

import datetime as dt
import logging
from collections import defaultdict

from allianceauth.eveonline.models import EveCharacter
from django.utils import timezone
from esi.models import Token

from .. import app_settings
from ..models import WalletDivision, WalletJournalEntry
from . import esi
from .http import polite_pause, session

logger = logging.getLogger(__name__)

PERIODS = ("day", "week", "month", "quarter")


# --- token -----------------------------------------------------------------------------

def corp_id() -> int:
    return int(app_settings.SHIPYARD_STRUCTURE_CORP_ID)


def scopes() -> list[str]:
    return list(app_settings.SHIPYARD_WALLET_SCOPES)


def token():
    """A valid token with the wallet scopes for a character of the structure corp, or None."""
    character_ids = list(EveCharacter.objects.filter(corporation_id=corp_id()).values_list("character_id", flat=True))
    if not character_ids:
        return None
    return (
        Token.objects.filter(character_id__in=character_ids)
        .require_scopes(scopes())
        .require_valid()
        .order_by("-created")
        .first()
    )


# --- refresh -----------------------------------------------------------------------------

def _journal_pages(division: int, access_token: str, known: set, max_pages: int = 50) -> list[dict]:
    """Journal entries of one division, newest first, stopping at the first page that brings nothing new."""
    path = f"/corporations/{corp_id()}/wallets/{int(division)}/journal/"
    first = esi._authed(path, access_token, {"page": 1})
    rows = list(first.json() or [])
    pages = min(int(first.headers.get("X-Pages") or 1), max_pages)
    new = [r for r in rows if int(r["id"]) not in known]
    out = list(new)
    page = 2
    while page <= pages and new:
        polite_pause()
        rows = list(esi._authed(path, access_token, {"page": page}).json() or [])
        new = [r for r in rows if int(r["id"]) not in known]
        out.extend(new)
        page += 1
    return out


def refresh() -> dict:
    """Pull divisions, balances and every new journal entry; resolve the names. Returns counts."""
    tok = token()
    if tok is None:
        raise RuntimeError("no token with the corporation wallet scopes for a character of the structure corp")
    access_token = tok.valid_access_token()
    cid = corp_id()
    # division names and balances
    names = {}
    try:
        data = esi._authed(f"/corporations/{cid}/divisions/", access_token).json() or {}
        for d in data.get("wallet") or []:
            names[int(d["division"])] = d.get("name") or f"Division {d['division']}"
    except Exception as exc:  # noqa: BLE001
        logger.info("division names not read: %s", exc)
    balances = {}
    for w in esi._authed(f"/corporations/{cid}/wallets/", access_token).json() or []:
        balances[int(w["division"])] = float(w.get("balance") or 0)
    now = timezone.now()
    for division in range(1, 8):
        WalletDivision.objects.update_or_create(
            corporation_id=cid, division=division,
            defaults={"name": names.get(division, f"Division {division}"), "balance": balances.get(division, 0.0), "fetched_at": now},
        )
    # the journal
    known = set(WalletJournalEntry.objects.filter(corporation_id=cid).values_list("entry_id", flat=True))
    added = 0
    for division in range(1, 8):
        try:
            rows = _journal_pages(division, access_token, known)
        except Exception as exc:  # noqa: BLE001
            logger.warning("journal of division %s failed: %s", division, exc)
            continue
        for r in rows:
            WalletJournalEntry.objects.update_or_create(
                entry_id=int(r["id"]),
                defaults={
                    "corporation_id": cid,
                    "division": division,
                    "date": dt.datetime.fromisoformat(str(r["date"]).replace("Z", "+00:00")),
                    "ref_type": r.get("ref_type") or "",
                    "amount": float(r.get("amount") or 0),
                    "balance": float(r.get("balance") or 0),
                    "first_party_id": int(r.get("first_party_id") or 0),
                    "second_party_id": int(r.get("second_party_id") or 0),
                    "context_id": int(r.get("context_id") or 0),
                    "context_id_type": r.get("context_id_type") or "",
                    "description": (r.get("description") or "")[:500],
                    "reason": (r.get("reason") or "")[:500],
                    "tax": float(r.get("tax") or 0),
                    "tax_receiver_id": int(r.get("tax_receiver_id") or 0),
                },
            )
            known.add(int(r["id"]))
            added += 1
        polite_pause()
    resolve_parties()
    return {"added": added, "total": len(known), "divisions": len(balances)}


def resolve_parties(limit: int = 500) -> int:
    """Fill party names and the payer's corporation for entries that lack them."""
    todo = list(WalletJournalEntry.objects.filter(first_party_name="").order_by("-date")[:limit])
    if not todo:
        return 0
    ids = set()
    for e in todo:
        ids.update(i for i in (e.first_party_id, e.second_party_id) if i)
    names = {}
    try:
        from eveuniverse.models import EveEntity
        resolver = EveEntity.objects.bulk_resolve_names(ids)
        names = {i: resolver.to_name(i) or "" for i in ids}
    except Exception as exc:  # noqa: BLE001
        logger.info("party names not resolved: %s", exc)
    # the payer's corporation: characters through ESI's affiliation list, corporations are their own
    categories = {}
    try:
        from eveuniverse.models import EveEntity
        categories = dict(EveEntity.objects.filter(id__in=ids).values_list("id", "category"))
    except Exception as exc:  # noqa: BLE001
        logger.info("entity categories not read: %s", exc)
    chars = [i for i in ids if categories.get(i) == "character" or (i not in categories and 90_000_000 <= i < 3_000_000_000)]
    corp_of = {i: i for i in ids if categories.get(i) == "corporation"}
    for i in range(0, len(chars), 1000):
        try:
            r = session().post("https://esi.evetech.net/latest/characters/affiliation/", json=chars[i:i + 1000], timeout=30)
            r.raise_for_status()
            for a in r.json():
                corp_of[int(a["character_id"])] = int(a.get("corporation_id") or 0)
        except Exception as exc:  # noqa: BLE001
            logger.info("affiliations not read: %s", exc)
    corp_names = {i: names.get(i, "") for i in corp_of.values() if i in names}
    corp_ids = {c for c in corp_of.values() if c and c not in corp_names}
    if corp_ids:
        try:
            from eveuniverse.models import EveEntity
            resolver = EveEntity.objects.bulk_resolve_names(corp_ids)
            corp_names.update({i: resolver.to_name(i) or "" for i in corp_ids})
        except Exception as exc:  # noqa: BLE001
            logger.info("corporation names not resolved: %s", exc)
    n = 0
    for e in todo:
        e.first_party_name = names.get(e.first_party_id) or (f"#{e.first_party_id}" if e.first_party_id else "")
        e.second_party_name = names.get(e.second_party_id) or (f"#{e.second_party_id}" if e.second_party_id else "")
        c = corp_of.get(e.first_party_id, 0)
        e.first_party_corp_id = c
        e.first_party_corp_name = corp_names.get(c, "") if c else ""
        e.save(update_fields=["first_party_name", "second_party_name", "first_party_corp_id", "first_party_corp_name"])
        n += 1
    return n


# --- analysis ----------------------------------------------------------------------------

def period_key(when: dt.datetime, period: str) -> str:
    d = when.date()
    if period == "day":
        return d.isoformat()
    if period == "week":
        monday = d - dt.timedelta(days=d.weekday())
        return f"{monday.isoformat()} (wk {monday.isocalendar()[1]})"
    if period == "month":
        return d.strftime("%Y-%m")
    if period == "quarter":
        return f"{d.year} Q{(d.month - 1) // 3 + 1}"
    return d.isoformat()


def income_entries(since=None):
    """Entries that are income for the structure corp: positive amounts of the configured ref types."""
    qs = WalletJournalEntry.objects.filter(corporation_id=corp_id(), amount__gt=0)
    types = list(app_settings.SHIPYARD_INCOME_REF_TYPES)
    if types:
        qs = qs.filter(ref_type__in=types)
    if since is not None:
        qs = qs.filter(date__gte=since)
    return qs.order_by("-date")


def pivot(entries, period: str) -> dict:
    """{'columns': [period keys newest first], 'rows': [(ref_type, {key: amount}, total)], 'totals': {key: amount}}"""
    cells = defaultdict(lambda: defaultdict(float))
    totals = defaultdict(float)
    keys = set()
    for e in entries:
        k = period_key(e.date, period)
        keys.add(k)
        cells[e.ref_type][k] += e.amount
        totals[k] += e.amount
    columns = sorted(keys, reverse=True)
    rows = sorted(((t, dict(v), sum(v.values())) for t, v in cells.items()), key=lambda r: -r[2])
    return {"columns": columns, "rows": rows, "totals": dict(totals)}


def payers(entries, period: str, recent_days: int = 30) -> list[dict]:
    """Who pays: one row per paying character with corporation, totals and the per-period amounts."""
    by = {}
    cutoff = timezone.now() - dt.timedelta(days=recent_days)
    for e in entries:
        row = by.setdefault(e.first_party_id, {
            "id": e.first_party_id, "name": e.first_party_name or f"#{e.first_party_id}",
            "corp_id": e.first_party_corp_id, "corp": e.first_party_corp_name,
            "total": 0.0, "recent": 0.0, "count": 0, "first": e.date, "last": e.date,
            "types": defaultdict(float), "periods": defaultdict(float),
        })
        row["total"] += e.amount
        row["count"] += 1
        if e.date >= cutoff:
            row["recent"] += e.amount
        row["first"] = min(row["first"], e.date)
        row["last"] = max(row["last"], e.date)
        row["types"][e.ref_type] += e.amount
        row["periods"][period_key(e.date, period)] += e.amount
    out = sorted(by.values(), key=lambda r: -r["total"])
    for r in out:
        r["types"] = sorted(r["types"].items(), key=lambda kv: -kv[1])
        r["periods"] = dict(r["periods"])
    return out


def totals(entries) -> dict:
    now = timezone.now()
    out = {"all": 0.0, "d7": 0.0, "d30": 0.0, "d90": 0.0, "count": 0, "first": None, "last": None}
    for e in entries:
        out["all"] += e.amount
        out["count"] += 1
        age = now - e.date
        if age <= dt.timedelta(days=7):
            out["d7"] += e.amount
        if age <= dt.timedelta(days=30):
            out["d30"] += e.amount
        if age <= dt.timedelta(days=90):
            out["d90"] += e.amount
        out["first"] = e.date if out["first"] is None or e.date < out["first"] else out["first"]
        out["last"] = e.date if out["last"] is None or e.date > out["last"] else out["last"]
    return out
