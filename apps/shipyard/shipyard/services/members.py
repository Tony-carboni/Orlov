"""Members who left, applied or were accepted (0.40.0, owner, 2026-11-14: "make a page on the front door with the
leaving members, available to myself and Hamu").

EVE tells only the CEO that a member left ("CharLeftCorpMsg"); directors get the application messages but not
that one, and the routing cannot be changed in game. So the Director page reads the CEO's character notifications
(ESI `/characters/{id}/notifications/`, scope `esi-characters.read_notifications.v1`, cached ten minutes by EVE,
the last few hundred kept) once an hour and stores every member message about the corporation as a
`CorpMemberEvent`, so the history outlives EVE's window. The CEO is read from the corporation's public record.
"""

import datetime as dt
import logging
import re

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from django.core.cache import cache
from esi.models import Token

from ..models import CorpMemberEvent, RefreshRun
from . import projects
from .http import session

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"
SCOPE = "esi-characters.read_notifications.v1"
KINDS = {  # EVE's notification type -> what it means for the roster
    "CharLeftCorpMsg": "left",
    "CorpAppNewMsg": "applied",
    "CharAppAcceptMsg": "accepted",
    "CharAppWithdrawMsg": "withdrawn",
    "CorpAppInvitedMsg": "invited",
}
LABELS = {"left": "left the corporation", "applied": "applied", "accepted": "application accepted", "withdrawn": "withdrew the application", "invited": "invited"}


def corp_id() -> int:
    return projects.corp_id()


def ceo_id(cid: int | None = None) -> int | None:
    """The corporation's CEO from EVE's public record, cached a day."""
    cid = cid or corp_id()
    key = f"shipyard:members:ceo:{cid}"
    v = cache.get(key)
    if v is None:
        r = session().get(f"{ESI}/corporations/{int(cid)}/", timeout=30)
        r.raise_for_status()
        v = int(r.json().get("ceo_id") or 0)
        cache.set(key, v, 86400)
    return v or None


def token(cid: int | None = None):
    """A valid notifications token of the CEO, or None."""
    ceo = ceo_id(cid)
    if not ceo:
        return None
    return Token.objects.filter(character_id=ceo).require_scopes([SCOPE]).require_valid().order_by("-created").first()


def parse(text: str) -> dict:
    """The fields of a notification's YAML-like text: charID, corpID, applicationText (first line of it). Pure."""
    out = {}
    for m in re.finditer(r"^(\w+):\s*(.*)$", text or "", re.M):
        out[m.group(1)] = m.group(2).strip().strip("'\"")
    return out


def names(ids) -> dict:
    ids = sorted({int(i) for i in ids if i})
    if not ids:
        return {}
    out = {}
    for i in range(0, len(ids), 500):
        r = session().post(f"{ESI}/universe/names/", json=ids[i:i + 500], timeout=30)
        if r.status_code == 200:
            out.update({int(x["id"]): x["name"] for x in r.json()})
    return out


def refresh() -> dict:
    """Store the CEO's member notifications about the corporation that are not stored yet."""
    cid = corp_id()
    tok = token(cid)
    if tok is None:
        raise RuntimeError("no CEO token with the notifications scope; the CEO registers through My settings (every scope)")
    headers = {"Authorization": f"Bearer {tok.valid_access_token()}", "Accept": "application/json"}
    r = session().get(f"{ESI}/characters/{int(tok.character_id)}/notifications/", headers=headers, timeout=30)
    r.raise_for_status()
    rows = [n for n in (r.json() or []) if n.get("type") in KINDS]
    known = set(CorpMemberEvent.objects.filter(corporation_id=cid).values_list("notification_id", flat=True))
    fresh = []
    for n in rows:
        f = parse(n.get("text", ""))
        if int(n["notification_id"]) in known or str(f.get("corpID", "")) != str(cid):
            continue
        fresh.append((n, f))
    by_id = names([f.get("charID") for _, f in fresh])
    made = []
    for n, f in fresh:
        char_id = int(f.get("charID") or 0)
        made.append(CorpMemberEvent(
            corporation_id=cid, notification_id=int(n["notification_id"]), kind=KINDS[n["type"]], character_id=char_id,
            character_name=by_id.get(char_id, EveCharacter.objects.filter(character_id=char_id).values_list("character_name", flat=True).first() or str(char_id)),
            timestamp=dt.datetime.fromisoformat(str(n["timestamp"]).replace("Z", "+00:00")),
            text=(f.get("applicationText") or "")[:500]))
    CorpMemberEvent.objects.bulk_create(made, ignore_conflicts=True)
    return {"new": len(made), "seen": len(rows), "character": tok.character_name}


def last_read():
    return RefreshRun.objects.filter(step="member_events", ok=True).order_by("-finished_at").first()


def leavers(cid: int | None = None, days: int = 0) -> list[dict]:
    """The Director page's rows, newest first: who left, when, what auth knows of them."""
    cid = cid or corp_id()
    qs = CorpMemberEvent.objects.filter(corporation_id=cid, kind="left").order_by("-timestamp")
    if days:
        qs = qs.filter(timestamp__gte=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days))
    events = list(qs)
    chars = {c.character_id: c for c in EveCharacter.objects.filter(character_id__in=[e.character_id for e in events])}
    owners = {o.character.character_id: o for o in CharacterOwnership.objects.filter(character__character_id__in=list(chars)).select_related("user__profile__main_character", "user__profile__state")}
    joined_after = {}  # character -> the newest acceptance after the leave (came back)
    for a in CorpMemberEvent.objects.filter(corporation_id=cid, kind="accepted", character_id__in=[e.character_id for e in events]).order_by("timestamp"):
        joined_after[a.character_id] = a.timestamp
    out = []
    for e in events:
        c = chars.get(e.character_id)
        o = owners.get(e.character_id)
        if o:
            main = o.user.profile.main_character
            auth = f"{o.user.username}: {'main' if main and main.character_id == e.character_id else 'alt of ' + (main.character_name if main else '?')}, {o.user.profile.state.name if o.user.profile.state else 'no state'}"
            auth += ", Discord linked" if hasattr(o.user, "discord") else ", no Discord"
        elif c:
            auth = "known to auth, no owner"
        else:
            auth = "never registered"
        now = ""
        if c and c.corporation_id == cid:
            now = "back in the corporation" if joined_after.get(e.character_id, e.timestamp) > e.timestamp else "auth still lists them in the corporation"
        elif c:
            now = f"now in {c.corporation_name or c.corporation_id}" + (f" [{c.alliance_ticker}]" if c.alliance_ticker else "")
        out.append({"when": e.timestamp, "character_id": e.character_id, "name": e.character_name, "auth": auth, "now": now, "returned": e.character_id in joined_after and joined_after[e.character_id] > e.timestamp})
    return out


def counts(cid: int | None = None, days: int = 30) -> dict:
    cid = cid or corp_id()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    out = {k: 0 for k in LABELS}
    for kind in CorpMemberEvent.objects.filter(corporation_id=cid, timestamp__gte=since).values_list("kind", flat=True):
        out[kind] = out.get(kind, 0) + 1
    return out
