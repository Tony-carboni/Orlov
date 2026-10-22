"""The LP log (owner, 2026-10-22): hourly readings of every character's loyalty points, kept as a log.

EVE keeps no history of loyalty points. ESI gives a character's balances per NPC corporation
(`/characters/{id}/loyalty/points/`, scope `esi-characters.read_loyalty.v1`, cached one hour), so the
best log possible is one reading an hour. The task reads every character with a valid token carrying
the scope (Member Audit's registration gives it) and writes an `LpSnapshot` row only when a balance
moved since the last reading: those rows are the log. A fall that coincides with a "Payment to LP
Store" line in Member Audit's copy of that character's wallet journal is noted with the ISK paid.
Gains and spends inside the same hour net against each other; that is the limit of hourly data.
"""

import logging
from collections import defaultdict

from django.utils import timezone
from esi.models import Token

from ..models import LpSnapshot
from .http import polite_pause, session
from .wallet import period_key

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"
SCOPE = "esi-characters.read_loyalty.v1"
PERIODS = ("day", "week", "month")


# --- reading ------------------------------------------------------------------------------

def tokens() -> dict:
    """{character_id: token}: one valid token per character that holds the loyalty scope."""
    out = {}
    for t in Token.objects.filter(scopes__name=SCOPE).require_valid().order_by("-created"):
        out.setdefault(t.character_id, t)
    return out


def read(character_id: int, token) -> dict:
    """{corporation_id: loyalty_points} as ESI reports it now."""
    headers = {"Authorization": f"Bearer {token.valid_access_token()}", "Accept": "application/json"}
    r = session().get(f"{ESI}/characters/{int(character_id)}/loyalty/points/", headers=headers, timeout=30)
    r.raise_for_status()
    return {int(x["corporation_id"]): int(x["loyalty_points"]) for x in r.json() or []}


def latest(character_id: int) -> dict:
    """{corporation_id: (loyalty_points, taken_at)}: the newest reading per corporation of this character."""
    out = {}
    qs = LpSnapshot.objects.filter(character_id=character_id).order_by("-taken_at").values_list("corporation_id", "loyalty_points", "taken_at")
    for corp, lp, at in qs:
        out.setdefault(corp, (lp, at))
    return out


def record(character_id: int, character_name: str, balances: dict, now=None) -> int:
    """Store what moved since the last reading; a first reading stores every balance. Returns rows written."""
    now = now or timezone.now()
    prev = latest(character_id)
    first = not prev
    last_run = max((at for _, at in prev.values()), default=None)
    rows = []

    def row(corp, lp, change, previous_at, is_first=False):
        rows.append(LpSnapshot(character_id=character_id, character_name=character_name, corporation_id=corp, loyalty_points=lp,
                               change=change, previous_at=previous_at, is_first=is_first, taken_at=now))

    for corp, lp in balances.items():
        old = prev.get(corp)
        if old is None:
            if first:
                row(corp, lp, 0, None, True)
            elif lp:
                row(corp, lp, lp, last_run)
        elif old[0] != lp:
            row(corp, lp, lp - old[0], old[1])
    for corp, (lp, at) in prev.items():
        if corp not in balances and lp:
            row(corp, 0, -lp, at)
    if rows:
        LpSnapshot.objects.bulk_create(rows)
    return len(rows)


def snapshot() -> dict:
    """Read every character with the scope and log the changes."""
    toks = tokens()
    read_ok = written = 0
    errors = []
    for cid, tok in toks.items():
        try:
            balances = read(cid, tok)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{tok.character_name}: {exc}")
            continue
        read_ok += 1
        written += record(cid, tok.character_name, balances)
        polite_pause()
    resolve_corporation_names()
    return {"characters": len(toks), "read": read_ok, "written": written, "errors": errors}


def resolve_corporation_names() -> int:
    todo = [c for c in LpSnapshot.objects.filter(corporation_name="").values_list("corporation_id", flat=True).distinct() if c]
    if not todo:
        return 0
    names = {}
    try:
        from eveuniverse.models import EveEntity

        resolver = EveEntity.objects.bulk_resolve_names(todo)
        names = {i: resolver.to_name(i) or "" for i in todo}
    except Exception as exc:  # noqa: BLE001
        logger.info("corporation names not resolved: %s", exc)
    n = 0
    for i, name in names.items():
        if name:
            n += LpSnapshot.objects.filter(corporation_id=i, corporation_name="").update(corporation_name=name)
    return n


def coverage(character_ids) -> dict:
    """Which of these characters the log can read: {logged: [names], missing: [names]}."""
    have = set(tokens())
    logged, missing = [], []
    try:
        from allianceauth.eveonline.models import EveCharacter

        names = dict(EveCharacter.objects.filter(character_id__in=list(character_ids)).values_list("character_id", "character_name"))
    except Exception:  # noqa: BLE001
        names = {}
    for cid in character_ids:
        (logged if cid in have else missing).append(names.get(cid, str(cid)))
    return {"logged": sorted(logged), "missing": sorted(missing)}


# --- the log ------------------------------------------------------------------------------

def log(character_ids=None, since=None, corporation_id=None, limit=None) -> list[dict]:
    """The readings as plain dicts, newest first, with LP store payments noted."""
    qs = LpSnapshot.objects.all()
    if character_ids is not None:
        qs = qs.filter(character_id__in=list(character_ids))
    if since is not None:
        qs = qs.filter(taken_at__gte=since)
    if corporation_id:
        qs = qs.filter(corporation_id=int(corporation_id))
    qs = qs.order_by("-taken_at", "character_name", "corporation_name")
    if limit:
        qs = qs[: int(limit)]
    rows = [{
        "at": r.taken_at, "previous_at": r.previous_at, "character_id": r.character_id, "character": r.character_name or str(r.character_id),
        "corporation_id": r.corporation_id, "corporation": r.corporation_name or str(r.corporation_id),
        "change": r.change, "balance": r.loyalty_points, "first": r.is_first, "note": "First reading" if r.is_first else "",
    } for r in qs]
    _note_store_payments(rows)
    return rows


def _note_store_payments(rows) -> None:
    """A fall between two readings that matches a 'Payment to LP Store' line to that corporation gets the ISK noted."""
    falls = [r for r in rows if r["change"] < 0 and r["previous_at"]]
    if not falls:
        return
    try:
        from memberaudit.models import CharacterWalletJournalEntry
    except Exception:  # noqa: BLE001
        return
    try:
        cids = {r["character_id"] for r in falls}
        lo = min(r["previous_at"] for r in falls)
        hi = max(r["at"] for r in falls)
        pays = defaultdict(list)
        qs = CharacterWalletJournalEntry.objects.filter(character__eve_character__character_id__in=list(cids), ref_type="lp_store", date__gt=lo, date__lte=hi)
        for cid, corp, date, amount in qs.values_list("character__eve_character__character_id", "second_party_id", "date", "amount"):
            pays[(cid, corp)].append((date, float(amount)))
    except Exception as exc:  # noqa: BLE001
        logger.info("LP store payments not read: %s", exc)
        return
    for r in falls:
        hits = [a for d, a in pays.get((r["character_id"], r["corporation_id"]), []) if r["previous_at"] < d <= r["at"]]
        if hits:
            r["note"] = f"LP store: {len(hits)} payment{'s' if len(hits) > 1 else ''}, {-sum(hits):,.0f} ISK"


def balances(character_ids=None) -> dict:
    """{corporation_id: {name, lp, characters}}: the newest reading per character and corporation, summed."""
    qs = LpSnapshot.objects.all()
    if character_ids is not None:
        qs = qs.filter(character_id__in=list(character_ids))
    seen = set()
    out = {}
    for cid, corp, name, lp in qs.order_by("-taken_at").values_list("character_id", "corporation_id", "corporation_name", "loyalty_points"):
        if (cid, corp) in seen:
            continue
        seen.add((cid, corp))
        b = out.setdefault(corp, {"name": name or str(corp), "lp": 0, "characters": 0})
        b["lp"] += lp
        b["characters"] += 1 if lp else 0
    return out


def summary(rows: list[dict], period: str, balances: dict | None = None) -> dict:
    """Per corporation: LP earned, spent, net, the balance now; per period: earned and spent per corporation. Pure."""
    balances = balances or {}
    corps = {}
    earned = defaultdict(lambda: defaultdict(int))
    spent = defaultdict(lambda: defaultdict(int))
    columns = set()
    for r in rows:
        c = corps.setdefault(r["corporation_id"], {"corporation_id": r["corporation_id"], "corporation": r["corporation"], "earned": 0, "spent": 0, "readings": 0, "characters": set()})
        c["readings"] += 1
        c["characters"].add(r["character"])
        if r["first"]:
            continue
        key = period_key(r["at"], period)
        columns.add(key)
        if r["change"] > 0:
            c["earned"] += r["change"]
            earned[r["corporation"]][key] += r["change"]
        elif r["change"] < 0:
            c["spent"] -= r["change"]
            spent[r["corporation"]][key] -= r["change"]
    for corp, b in balances.items():
        c = corps.setdefault(corp, {"corporation_id": corp, "corporation": b["name"], "earned": 0, "spent": 0, "readings": 0, "characters": set()})
        c["balance"] = b["lp"]
    out = []
    for c in corps.values():
        c["net"] = c["earned"] - c["spent"]
        c["characters"] = len(c["characters"])
        c.setdefault("balance", None)
        out.append(c)
    out.sort(key=lambda c: -(c["earned"] + c["spent"]))
    cols = sorted(columns)
    datasets = []
    for name in sorted(set(earned) | set(spent)):
        datasets.append({"label": f"{name} earned", "data": [earned[name].get(k, 0) for k in cols]})
        datasets.append({"label": f"{name} spent", "data": [-spent[name].get(k, 0) for k in cols]})
    return {
        "corporations": out,
        "earned": sum(c["earned"] for c in out), "spent": sum(c["spent"] for c in out),
        "changes": sum(1 for r in rows if not r["first"]),
        "chart": {"labels": cols, "datasets": datasets},
    }
