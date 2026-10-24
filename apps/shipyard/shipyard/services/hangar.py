"""The projects hangar as EVE shows it (owner's rule, 2026-10-23).

The goods held from project buybacks are what is physically in the corporation's projects hangar: if it is not
in that hangar it is not in stock. The hourly task reads the corporation's assets (ESI, scope
`esi-assets.read_corporation_assets.v1`, a Director's token: the CEO's), keeps the corp hangar divisions
(CorpSAG1 to CorpSAG7), the deliveries hangar and the Projects hangar (CorporationGoalDeliveries), and stores one row per item type, office and division.
The balance sheet (services/books.py) then counts the goods from these rows, at what the projects paid for
them (the ledger's lots, oldest first); the stock batches (cap boosters, Heavy Water) are not in this hangar
and stay ledger-style. The projects hangar is, by default, the office the corporation projects deliver to (EVE
records it in each project's configuration, `deliver_item.office_id`), every hangar division there (0.28.0;
the owner's rule: section 1 counts the actual content of the projects hangar and nothing else). The settings
SHIPYARD_BOOKS_HANGAR_LOCATIONS and SHIPYARD_BOOKS_HANGAR_FLAGS override that when set.
"""

import datetime as dt
import logging
from collections import defaultdict

from allianceauth.eveonline.models import EveCharacter
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from esi.models import Token

from .. import app_settings
from ..models import CorpProject, HangarItem
from . import esi, projects

logger = logging.getLogger(__name__)

DIVISIONS = {f"CorpSAG{i}": f"hangar division {i}" for i in range(1, 8)}
DIVISIONS["CorpDeliveries"] = "deliveries"
PROJECTS_FLAG = "CorporationGoalDeliveries"  # the game's "Projects" hangar under Corporation hangars (0.31.1), where project deliveries land
DIVISIONS[PROJECTS_FLAG] = "projects hangar"


def corp_id() -> int:
    return projects.corp_id()


def scopes() -> list[str]:
    """The scopes the connect button asks for: the production scopes plus the hangar scope, so one token serves all."""
    return list(dict.fromkeys(list(app_settings.SHIPYARD_PRODUCTION_SCOPES) + list(app_settings.SHIPYARD_HANGAR_SCOPES)))


def token():
    """A valid token with the hangar scope for a character of the corporation, or None."""
    ids = list(EveCharacter.objects.filter(corporation_id=corp_id()).values_list("character_id", flat=True))
    if not ids:
        return None
    return Token.objects.filter(character_id__in=ids).require_scopes(list(app_settings.SHIPYARD_HANGAR_SCOPES)).require_valid().order_by("-created").first()


def aggregate(rows) -> dict:
    """{(type_id, location_id, flag): quantity} of the corp hangar rows in an ESI assets list. Pure."""
    out = defaultdict(int)
    for a in rows:
        flag = str(a.get("location_flag") or "")
        if flag not in DIVISIONS:
            continue
        qty = int(a.get("quantity") or 0)
        if a.get("is_singleton") and qty <= 0:
            qty = 1
        out[(int(a["type_id"]), int(a.get("location_id") or 0), flag)] += qty
    return dict(out)


EXPIRES_KEY = "shipyard:hangar:expires"  # when EVE's copy of the assets is renewed (the Expires header of the last read)


def _read_assets(cid: int, access_token: str, max_pages: int = 50) -> tuple:
    """(rows, expires): every page of the corporation's assets and the moment EVE renews its copy."""
    path = f"/corporations/{int(cid)}/assets/"
    first = esi._authed(path, access_token, {"page": 1})
    rows = list(first.json() or [])
    pages = min(int(first.headers.get("X-Pages") or 1), max_pages)
    for page in range(2, pages + 1):
        rows.extend(esi._authed(path, access_token, {"page": page}).json() or [])
    expires = None
    try:
        from email.utils import parsedate_to_datetime

        expires = parsedate_to_datetime(first.headers["Expires"]) if first.headers.get("Expires") else None
    except (TypeError, ValueError, KeyError):
        expires = None
    return rows, expires


def refresh() -> dict:
    """Read the corporation's assets and replace the hangar rows."""
    tok = token()
    if tok is None:
        raise RuntimeError("no token with the corporation assets scope for a character of the corporation")
    cid = corp_id()
    rows, expires = _read_assets(cid, tok.valid_access_token())
    if expires is not None:
        cache.set(EXPIRES_KEY, expires.isoformat(), 3 * 3600)
    agg = aggregate(rows)
    now = timezone.now()
    from .projectbooks import _names

    names = _names({t for t, _, _ in agg})
    items = [HangarItem(corporation_id=cid, type_id=t, name=names.get(t, ""), quantity=q, location_id=loc, location_flag=flag, read_at=now)
             for (t, loc, flag), q in agg.items()]
    with transaction.atomic():
        HangarItem.objects.filter(corporation_id=cid).delete()
        HangarItem.objects.bulk_create(items)
    return {"assets": len(rows), "rows": len(items), "types": len({t for t, _, _ in agg}), "read_at": now, "character": tok.character_name}


def schedule(now=None, read_at=None) -> dict:
    """The clock on the Finance tab (owner, 2026-10-24): when the hangar was last read, when EVE renews its copy
    (the Expires header of that read) and when the next hourly read runs (the beat entry's minute). The next
    read only shows a change when EVE's copy has been renewed by then."""
    now = now or timezone.now()
    minute = int(app_settings.SHIPYARD_HANGAR_BEAT_MINUTE)
    next_run = now.replace(minute=minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += dt.timedelta(hours=1)
    fresh_at = None
    raw = cache.get(EXPIRES_KEY)
    if raw:
        try:
            fresh_at = dt.datetime.fromisoformat(raw)
        except ValueError:
            fresh_at = None
    if read_at is None:
        read_at = HangarItem.objects.filter(corporation_id=corp_id()).values_list("read_at", flat=True).first()
    # the first automatic read that sees renewed data
    effective = next_run
    if fresh_at is not None:
        while effective < fresh_at:
            effective += dt.timedelta(hours=1)
    return {"read_at": read_at, "fresh_at": fresh_at, "next_run": next_run, "effective": effective, "now": now,
            "cached": fresh_at is not None and fresh_at > now}


def project_offices(cid=None) -> set:
    """The offices the corporation projects deliver to: the projects hangar by EVE's own record."""
    cid = cid or corp_id()
    out = set()
    for details in CorpProject.objects.filter(corporation_id=cid).exclude(details=None).values_list("details", flat=True):
        cfg = (details or {}).get("configuration") or {}
        di = cfg.get("deliver_item") if isinstance(cfg, dict) else None
        if di and di.get("office_id"):
            out.add(int(di["office_id"]))
    return out


def scope(cid=None) -> tuple:
    """(location ids, flags) that count as the projects hangar: the settings when set, else the game's own Projects
    hangar (flag CorporationGoalDeliveries) at the offices the projects deliver to. 0.31.1: until then every hangar
    division at the office counted, which took the DIRECTOR-REPROCESS tab for the projects hangar."""
    locs = {int(x) for x in app_settings.SHIPYARD_BOOKS_HANGAR_LOCATIONS or []} or project_offices(cid)
    flags = set(app_settings.SHIPYARD_BOOKS_HANGAR_FLAGS or []) or {PROJECTS_FLAG}
    return locs, flags


def _wanted(location_id, flag, scope_=None) -> bool:
    locs, flags = scope_ or scope()
    return (not locs or int(location_id) in locs) and (not flags or flag in flags)


def stock(cid=None) -> tuple:
    """({type_id: units} in the projects hangar, {type_id: name}, read_at or None when never read)."""
    cid = cid or corp_id()
    units, names, read_at = defaultdict(int), {}, None
    sc = scope(cid)
    for h in HangarItem.objects.filter(corporation_id=cid):
        read_at = h.read_at
        if _wanted(h.location_id, h.location_flag, sc):
            units[h.type_id] += h.quantity
            if h.name:
                names[h.type_id] = h.name
    return dict(units), names, read_at


def divisions(cid=None) -> list:
    """What the last read found, per office and division: for choosing the projects hangar."""
    cid = cid or corp_id()
    rows = defaultdict(lambda: {"types": 0, "units": 0, "wanted": False, "sample": []})
    sc = scope(cid)
    for h in HangarItem.objects.filter(corporation_id=cid).order_by("-quantity"):
        r = rows[(h.location_id, h.location_flag)]
        r["types"] += 1
        r["units"] += h.quantity
        r["wanted"] = _wanted(h.location_id, h.location_flag, sc)
        if len(r["sample"]) < 4:
            r["sample"].append(h.name or str(h.type_id))
    return [{"location_id": loc, "flag": flag, "division": DIVISIONS.get(flag, flag), **r} for (loc, flag), r in sorted(rows.items())]
