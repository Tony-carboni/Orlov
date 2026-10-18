"""SRP: ship replacement requests, from the kill feed or by hand, paid out of the SRP wallet.

The story (owner, 2026-10-18): a pilot who loses a ship on an SRP fleet replies "SRP" to the
loss in #zkillboard. The bot creates a request here; the payout is the doctrine's figure for
that fit (cost of the doctrine fitting at Jita × the SRP percentage), never the killmail's
value, so cargo and odd modules cannot inflate it. A loss that is not a doctrine fit becomes
an **ad-hoc** request for an SRP agent to review. The zKillboard kill id keeps requests
unique. Once the SRP wallet (division 2) shows the ISK going out with the kill id in the
reason, the request is marked paid, by the hourly matcher or by hand.
"""

import datetime as dt
import logging
import re
from collections import Counter

import requests
from django.conf import settings
from django.utils import timezone

from .. import app_settings
from ..models import DoctrineShip, SrpRequest
from . import fittings

logger = logging.getLogger(__name__)

ZKB_API = "https://zkillboard.com/api/killID/{}/"
ESI = "https://esi.evetech.net/latest"
HEADERS = {"User-Agent": "orlov-auth doctrines SRP (auth.orlovfamily.space)", "Accept-Encoding": "gzip"}
TIMEOUT = 20
# inventory flags of fitted modules: low 11-18, mid 19-26, high 27-34, rigs 92-99, subsystems 125-132
FITTED_FLAGS = set(range(11, 35)) | set(range(92, 100)) | set(range(125, 133))
KILL_URL = re.compile(r"zkillboard\.com/kill/(\d+)", re.I)
KILL_ID = re.compile(r"(?<!\d)(\d{6,})(?!\d)")


class SrpError(Exception):
    pass


def kill_id_from(text: str) -> int | None:
    """The kill id in a zKillboard link or a bare number."""
    text = (text or "").strip()
    m = KILL_URL.search(text)
    if m:
        return int(m.group(1))
    if text.isdigit():
        return int(text)
    return None


# --- the kill ----------------------------------------------------------------------------------

def fetch_kill(kill_id: int) -> dict:
    """The killmail from zKillboard (for the hash and the values) and EVE (for the victim and the items)."""
    r = requests.get(ZKB_API.format(kill_id), headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    listing = r.json() or []
    if not listing:
        raise SrpError(f"zKillboard does not know kill {kill_id}")
    zkb = listing[0].get("zkb") or {}
    kill_hash = zkb.get("hash")
    if not kill_hash:
        raise SrpError(f"zKillboard gives no hash for kill {kill_id}")
    r = requests.get(f"{ESI}/killmails/{kill_id}/{kill_hash}/", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    killmail = r.json()
    killmail["zkb"] = zkb
    return killmail


def names_of(ids) -> dict:
    """Names for EVE ids (characters, corporations, alliances, types, systems) from EVE; {} when EVE does not answer."""
    ids = sorted({int(i) for i in ids if i})
    if not ids:
        return {}
    try:
        r = requests.post(f"{ESI}/universe/names/", json=ids[:1000], headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return {row["id"]: row["name"] for row in r.json()}
    except Exception as exc:  # noqa: BLE001
        logger.warning("SRP: names not resolved: %s", exc)
        return {}


def fitted_type_ids(victim: dict) -> list[int]:
    """The type ids fitted on the lost ship (modules, rigs, subsystems), one per unit."""
    out = []
    for item in victim.get("items") or []:
        if int(item.get("flag", -1)) not in FITTED_FLAGS:
            continue
        qty = int(item.get("quantity_destroyed", 0) or 0) + int(item.get("quantity_dropped", 0) or 0)
        out.extend([int(item["item_type_id"])] * max(qty, 1))
    return out


# --- the doctrine match --------------------------------------------------------------------------

def doctrine_modules(ship: DoctrineShip) -> Counter:
    """type id → units of the doctrine fit's modules, rigs and subsystems (charges, drones, cargo left out)."""
    needed = Counter()
    for slot in ("high", "mid", "low", "rig", "subsystem"):
        for row in (ship.fitting_json or {}).get("slots", {}).get(slot, []):
            needed[int(row["type_id"])] += int(row.get("quantity", 1))
    return needed


def match(ship_type_id: int, fitted: list[int]):
    """The doctrine fit that matches the lost ship best: (ship, score, missing Counter).
    score = share of the doctrine's module units that were fitted; 1.0 = the doctrine fit (extra
    modules on the lost ship do not count against it). (None, 0, Counter()) when no active doctrine
    carries the hull."""
    have = Counter(fitted)
    best = (None, 0.0, Counter())
    candidates = DoctrineShip.objects.filter(is_active=True, doctrine__is_active=True, ship_type_id=ship_type_id).select_related("doctrine").order_by("doctrine__order", "order", "id")
    for ship in candidates:
        needed = doctrine_modules(ship)
        total = sum(needed.values())
        matched = sum(min(n, have.get(t, 0)) for t, n in needed.items())
        score = matched / total if total else 1.0
        missing = Counter({t: n - have.get(t, 0) for t, n in needed.items() if n > have.get(t, 0)})
        if best[0] is None or score > best[1]:
            best = (ship, score, missing)
    return best


def alliance_ids() -> set[int]:
    ids = set(getattr(settings, "DOCTRINES_SRP_ALLIANCE_IDS", []) or [])
    ids |= set(getattr(settings, "ORLOVBOT_KILLFEED_ALLIANCE_IDS", []) or [])
    return {int(i) for i in ids}


# --- the request ---------------------------------------------------------------------------------

def create_from_kill(kill_id: int, requested_by: str = "", discord_id=None, message_id=None, source: str = "discord"):
    """Record the loss as an SRP request. Returns (request, created); created is False when the
    kill id was requested before (the existing request comes back unchanged)."""
    existing = SrpRequest.objects.filter(kill_id=kill_id).first()
    if existing:
        return existing, False
    killmail = fetch_kill(kill_id)
    victim = killmail.get("victim") or {}
    ship_type_id = int(victim.get("ship_type_id") or 0)
    names = names_of([victim.get("character_id"), victim.get("corporation_id"), victim.get("alliance_id"), ship_type_id, killmail.get("solar_system_id")])
    fitted = fitted_type_ids(victim)
    ship, score, missing = match(ship_type_id, fitted)
    reasons = []
    if ship is None:
        reasons.append(f"no active doctrine carries a {names.get(ship_type_id, 'ship of this type')}")
    elif missing:
        missing_names = names_of(list(missing))
        parts = [f"{n} × {missing_names.get(t, t)}" if n > 1 else str(missing_names.get(t, t)) for t, n in missing.items()]
        reasons.append(f"{sum(missing.values())} doctrine module(s) not fitted: " + ", ".join(parts[:6]) + (" …" if len(parts) > 6 else ""))
    allowed = alliance_ids()
    if allowed and int(victim.get("alliance_id") or 0) not in allowed:
        reasons.append("the pilot is not in the alliance")
    doctrine_cost = srp_percent = payout = None
    match_note = ""
    if ship is not None:
        row = fittings.page_data([ship], ship.doctrine.srp_percent)[0]
        doctrine_cost = row["cost"]["total"] or None
        srp_percent = row["srp_percent"]
        payout = round(row["srp"]) if row["srp"] else None
        match_note = f"{ship.doctrine.name}: {ship.name}, {int(round(score * 100))} % of the doctrine modules fitted"
        if row["cost"]["missing"]:
            reasons.append(f"{len(row['cost']['missing'])} doctrine item(s) without a price yet")
    when = killmail.get("killmail_time")
    try:
        kill_time = dt.datetime.fromisoformat(when.replace("Z", "+00:00")) if when else timezone.now()
    except ValueError:
        kill_time = timezone.now()
    zkb = killmail.get("zkb") or {}
    record = SrpRequest.objects.create(
        kill_id=kill_id, kill_hash=zkb.get("hash", ""), kill_time=kill_time,
        system_name=names.get(killmail.get("solar_system_id"), ""),
        pilot_id=int(victim.get("character_id") or 0), pilot_name=names.get(victim.get("character_id"), "") or "unknown",
        corporation_name=names.get(victim.get("corporation_id"), ""),
        ship_type_id=ship_type_id, ship_type_name=names.get(ship_type_id, "") or f"type {ship_type_id}",
        doctrine=ship.doctrine if ship else None, doctrine_ship=ship, match_score=score, match_note=match_note,
        adhoc=bool(reasons), adhoc_reason="; ".join(reasons),
        status=SrpRequest.REVIEW if reasons else SrpRequest.OPEN,
        zkb_value=float(zkb.get("totalValue") or 0), fitted_value=float(zkb.get("fittedValue") or 0),
        doctrine_cost=doctrine_cost, srp_percent=srp_percent, payout=payout,
        requested_by=requested_by[:100], requested_by_discord_id=discord_id, discord_message_id=message_id, source=source,
    )
    logger.info("SRP: request %s for kill %s (%s, %s) %s", record.pk, kill_id, record.pilot_name, record.ship_type_name, record.status)
    return record, True


# --- the payments --------------------------------------------------------------------------------

def wallet_token():
    """A token that can read the corporation's wallets: the Shipyard's production-corp token (Catherine Frey)."""
    try:
        from shipyard.services import business
    except ImportError:
        return None
    try:
        return business.token()
    except Exception:  # noqa: BLE001
        return None


def read_journal(token, pages: int = 3) -> list[dict]:
    corp = app_settings.DOCTRINES_SRP_CORP_ID
    division = app_settings.DOCTRINES_SRP_WALLET_DIVISION
    headers = dict(HEADERS, Authorization=f"Bearer {token.valid_access_token()}")
    out = []
    for page in range(1, pages + 1):
        r = requests.get(f"{ESI}/corporations/{corp}/wallets/{division}/journal/", params={"page": page}, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        rows = r.json() or []
        out.extend(rows)
        if int(r.headers.get("X-Pages", "1") or 1) <= page or not rows:
            break
    return out


def match_payments(journal: list[dict] | None = None) -> dict:
    """Mark open requests paid when the SRP wallet's journal shows ISK going out with the kill id in
    the reason (or the description). journal=None reads it from EVE with the wallet token."""
    if journal is None:
        token = wallet_token()
        if token is None:
            return {"ok": False, "matched": 0, "message": "no token with the corporation wallet scope (Catherine Frey: connect the jobs on My business)"}
        journal = read_journal(token)
    pending = {r.kill_id: r for r in SrpRequest.objects.filter(status__in=[SrpRequest.OPEN, SrpRequest.REVIEW])}
    matched = 0
    for entry in journal:
        amount = float(entry.get("amount") or 0)
        if amount >= 0:
            continue
        text = f"{entry.get('reason') or ''} {entry.get('description') or ''}"
        for found in KILL_ID.findall(text):
            record = pending.pop(int(found), None)
            if record is None:
                continue
            when = entry.get("date")
            try:
                paid_at = dt.datetime.fromisoformat(when.replace("Z", "+00:00")) if when else timezone.now()
            except ValueError:
                paid_at = timezone.now()
            record.mark_paid(amount=-amount, journal_id=entry.get("id"), note=f"{entry.get('ref_type', '')} seen in the SRP wallet", when=paid_at, by="wallet")
            matched += 1
            logger.info("SRP: request %s paid, journal %s, %.0f ISK", record.pk, entry.get("id"), -amount)
    return {"ok": True, "matched": matched, "entries": len(journal), "message": f"{matched} request(s) matched in {len(journal)} journal entries"}
