"""The executor corp's own books: its wallet journal and market transactions, kept as our copy.

ESI serves a corporation's journal and transactions for about a month. The hourly projects task
also copies every new journal entry of Orlov Arms International (OARMI) into CorpJournalEntry (its
own table: a transfer between two corps has the same entry id in both journals, so it cannot share
the structure corp's table) and every market transaction into CorpWalletTransaction, so the Corp projects tab can match what the corp sold
against what its projects bought from members (services/projectbooks.py, owner's request 2026-10-18).

Token: a valid token with the corporation wallet scope for a character of the executor corp
(Catherine Frey's production token carries it since 2026-10-18).
"""

import datetime as dt
import logging

from allianceauth.eveonline.models import EveCharacter
from esi.models import Token

from .. import app_settings
from ..models import CorpJournalEntry, CorpWalletTransaction
from . import esi
from .http import polite_pause

logger = logging.getLogger(__name__)

SCOPE = "esi-wallet.read_corporation_wallets.v1"
DIVISIONS = range(1, 8)


def corp_id() -> int:
    return int(app_settings.SHIPYARD_PROJECTS_CORP_ID)


def token():
    ids = list(EveCharacter.objects.filter(corporation_id=corp_id()).values_list("character_id", flat=True))
    if not ids:
        return None
    return Token.objects.filter(character_id__in=ids).require_scopes([SCOPE]).require_valid().order_by("-created").first()


def _when(value):
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _journal(division: int, access_token: str, known: set, max_pages: int = 50) -> list[dict]:
    """New journal entries of one division, newest first, stopping at a page that brings nothing new."""
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
    """Copy new journal entries and market transactions of every division. Returns counts."""
    tok = token()
    if tok is None:
        raise RuntimeError("no token with the corporation wallet scope for a character of the executor corp")
    access_token = tok.valid_access_token()
    cid = corp_id()
    known = set(CorpJournalEntry.objects.filter(corporation_id=cid).values_list("entry_id", flat=True))
    known_tx = set(CorpWalletTransaction.objects.filter(corporation_id=cid).values_list("transaction_id", flat=True))
    added = added_tx = 0
    for division in DIVISIONS:
        try:
            rows = _journal(division, access_token, known)
        except Exception as exc:  # noqa: BLE001
            logger.warning("journal of division %s failed: %s", division, exc)
            rows = []
        for r in rows:
            CorpJournalEntry.objects.update_or_create(
                corporation_id=cid, entry_id=int(r["id"]),
                defaults={
                    "division": division, "date": _when(r["date"]),
                    "ref_type": r.get("ref_type") or "", "amount": float(r.get("amount") or 0),
                    "balance": float(r.get("balance") or 0), "first_party_id": int(r.get("first_party_id") or 0),
                    "second_party_id": int(r.get("second_party_id") or 0), "context_id": int(r.get("context_id") or 0),
                    "context_id_type": r.get("context_id_type") or "", "description": (r.get("description") or "")[:500],
                    "reason": (r.get("reason") or "")[:500], "tax": float(r.get("tax") or 0),
                    "tax_receiver_id": int(r.get("tax_receiver_id") or 0),
                },
            )
            known.add(int(r["id"]))
            added += 1
        polite_pause()
        try:
            txs = list(esi._authed(f"/corporations/{cid}/wallets/{division}/transactions/", access_token).json() or [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("transactions of division %s failed: %s", division, exc)
            txs = []
        for t in txs:
            tid = int(t["transaction_id"])
            if tid in known_tx:
                continue
            CorpWalletTransaction.objects.create(
                transaction_id=tid, corporation_id=cid, division=division, date=_when(t["date"]),
                type_id=int(t["type_id"]), quantity=int(t.get("quantity") or 0), unit_price=float(t.get("unit_price") or 0),
                is_buy=bool(t.get("is_buy")), client_id=int(t.get("client_id") or 0), location_id=int(t.get("location_id") or 0),
                journal_ref_id=int(t.get("journal_ref_id") or 0),
            )
            known_tx.add(tid)
            added_tx += 1
        polite_pause()
    return {"journal": added, "transactions": added_tx}
