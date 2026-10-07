"""The member's own industry: jobs, blueprints and stock, read from ESI per character.

Every character of a member with a full-scope token is read: industry jobs (every
30 minutes), blueprints and assets (every 6 hours), by the background task and on the
fly when the page is opened or on "Refresh now". Assets are kept only for the types the
Shipyard knows (catalog ships, their blueprints, build materials, tags), rolled up to the
station or structure they sit in.

Who sees what (owner's rule 2026-10-07): a member sees their own characters; with
`view_corp_industry` (Corp Director) everyone whose character is in the member's corp;
with `view_alliance_industry` (Alliance Director) everyone in the alliance.
docs/runbooks/14-shipyards-front-door.md
"""

import collections
import datetime as dt
import logging

from allianceauth.eveonline.models import EveCharacter
from django.db import transaction
from django.utils import timezone

from .. import constants
from ..models import (
    BuildSnapshot, CharacterAsset, CharacterBlueprint, CharacterSync, IndustryJob, LocationName,
    MarketLocation, MaterialType, PriceSnapshot, Ship, ShipConfig,
)
from . import characters, esi

logger = logging.getLogger(__name__)

STALE_AFTER = {
    "jobs": dt.timedelta(minutes=30),
    "blueprints": dt.timedelta(hours=6),
    "assets": dt.timedelta(hours=6),
}
ACTIVE_STATUSES = ("active", "paused")
READY_STATUS = "ready"
RECENT_DAYS = 7
MAX_LIVE_BUILDS = 25  # dashboard: at most this many ships are recalculated with the member's own ME
STATION_RANGE = (60_000_000, 64_000_000)
STRUCTURE_MIN = 1_000_000_000_000
SCOPES = ("own", "corp", "alliance")


def _parse(ts):
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None


def is_stale(moment, section: str) -> bool:
    return moment is None or timezone.now() - moment > STALE_AFTER[section]


def relevant_type_ids() -> set:
    """Everything the Shipyard knows by type: ships, their blueprints, materials, tags."""
    ids = set()
    for type_id, bp_id in Ship.objects.filter(is_active=True).values_list("type_id", "blueprint_type_id"):
        ids.add(int(type_id))
        ids.add(int(bp_id))
    for mats in BuildSnapshot.objects.values_list("materials", flat=True):
        ids.update(int(m["type_id"]) for m in mats)
    ids.update(int(t) for t in ShipConfig.objects.exclude(tag_type_id=None).values_list("tag_type_id", flat=True))
    return ids


# --- reading from ESI ------------------------------------------------------------

def sync_user(user, force: bool = False) -> list[str]:
    """Read every character of the member that has full access. Returns notices for the page."""
    notices = []
    for ownership in user.character_ownerships.select_related("character"):
        character = ownership.character
        token = characters.token_for(user, character.character_id)
        if token is None:
            continue
        try:
            errors = sync_character(user, character, token, force=force)
        except Exception as exc:  # noqa: BLE001
            logger.warning("industry sync of %s failed: %s", character.character_name, exc)
            errors = [str(exc)[:120]]
        for error in errors:
            notices.append(f"{character.character_name}: {error}")
    return notices


def sync_all(force: bool = False) -> tuple[int, int]:
    """Background: every character already known to the page. Returns (characters, errors)."""
    done, failed = 0, 0
    for sync in CharacterSync.objects.select_related("user").order_by("pk"):
        character = EveCharacter.objects.filter(character_id=sync.character_id).first()
        token = characters.token_for(sync.user, sync.character_id)
        if character is None or token is None:
            continue
        try:
            errors = sync_character(sync.user, character, token, force=force)
        except Exception as exc:  # noqa: BLE001
            logger.warning("industry sync of %s failed: %s", sync.character_name, exc)
            errors = [str(exc)]
        done += 1
        failed += 1 if errors else 0
    return done, failed


def sync_character(user, eve_character, token, force: bool = False) -> list[str]:
    cid = eve_character.character_id
    sync, _ = CharacterSync.objects.get_or_create(
        user=user, character_id=cid, defaults={"character_name": eve_character.character_name}
    )
    sync.character_name = eve_character.character_name
    access_token = token.valid_access_token()
    errors = []

    if force or is_stale(sync.jobs_at, "jobs"):
        try:
            _store_jobs(user, cid, eve_character.character_name, esi.character_industry_jobs(cid, access_token))
            levels = esi.character_skill_levels(cid, access_token, constants.SLOT_SKILLS_ALL)
            sync.manufacturing_slots = 1 + sum(levels.get(s, 0) for s in constants.SLOT_SKILLS["manufacturing"])
            sync.science_slots = 1 + sum(levels.get(s, 0) for s in constants.SLOT_SKILLS["science"])
            sync.jobs_at = timezone.now()
        except Exception as exc:  # noqa: BLE001
            logger.warning("jobs of %s not read: %s", eve_character.character_name, exc)
            errors.append("industry jobs could not be read from EVE")

    if force or is_stale(sync.blueprints_at, "blueprints"):
        try:
            _store_blueprints(user, cid, esi.character_blueprints(cid, access_token))
            sync.blueprints_at = timezone.now()
        except Exception as exc:  # noqa: BLE001
            logger.warning("blueprints of %s not read: %s", eve_character.character_name, exc)
            errors.append("blueprints could not be read from EVE")

    if force or is_stale(sync.assets_at, "assets"):
        try:
            _store_assets(user, cid, esi.character_assets(cid, access_token))
            sync.assets_at = timezone.now()
        except Exception as exc:  # noqa: BLE001
            logger.warning("assets of %s not read: %s", eve_character.character_name, exc)
            errors.append("assets could not be read from EVE")

    sync.last_error = "; ".join(errors)[:300]
    sync.save()

    type_ids = set(IndustryJob.objects.filter(character_id=cid).values_list("product_type_id", flat=True))
    type_ids |= set(IndustryJob.objects.filter(character_id=cid).values_list("blueprint_type_id", flat=True))
    type_ids |= set(CharacterBlueprint.objects.filter(character_id=cid).values_list("type_id", flat=True))
    type_ids |= set(CharacterAsset.objects.filter(character_id=cid).values_list("type_id", flat=True))
    ensure_type_names(type_ids)
    location_ids = set(IndustryJob.objects.filter(character_id=cid).values_list("location_id", flat=True))
    location_ids |= set(CharacterBlueprint.objects.filter(character_id=cid).values_list("location_id", flat=True))
    location_ids |= set(CharacterAsset.objects.filter(character_id=cid).values_list("location_id", flat=True))
    ensure_location_names(location_ids, access_token)
    return errors


@transaction.atomic
def _store_jobs(user, character_id: int, character_name: str, jobs: list) -> int:
    IndustryJob.objects.filter(character_id=character_id).delete()
    rows = []
    for job in jobs:
        rows.append(IndustryJob(
            job_id=int(job["job_id"]), user=user, character_id=character_id, character_name=character_name,
            activity_id=int(job.get("activity_id") or 0),
            blueprint_type_id=int(job.get("blueprint_type_id") or 0),
            product_type_id=int(job["product_type_id"]) if job.get("product_type_id") else None,
            runs=int(job.get("runs") or 0),
            licensed_runs=int(job["licensed_runs"]) if job.get("licensed_runs") is not None else None,
            status=str(job.get("status") or ""),
            start_date=_parse(job.get("start_date")), end_date=_parse(job.get("end_date")),
            location_id=int(job.get("facility_id") or job.get("station_id") or job.get("location_id") or 0),
            cost=float(job.get("cost") or 0),
        ))
    IndustryJob.objects.bulk_create(rows)
    return len(rows)


@transaction.atomic
def _store_blueprints(user, character_id: int, blueprints: list) -> int:
    CharacterBlueprint.objects.filter(character_id=character_id).delete()
    rows = [
        CharacterBlueprint(
            item_id=int(b["item_id"]), user=user, character_id=character_id, type_id=int(b["type_id"]),
            location_id=int(b.get("location_id") or 0), location_flag=str(b.get("location_flag") or "")[:50],
            me=int(b.get("material_efficiency") or 0), te=int(b.get("time_efficiency") or 0),
            runs=int(b.get("runs") or -1), quantity=int(b.get("quantity") or 0),
        )
        for b in blueprints
    ]
    CharacterBlueprint.objects.bulk_create(rows)
    return len(rows)


def root_location(item: dict, by_item: dict) -> int:
    """Walk out of containers and ship holds to the station or structure an item sits in."""
    location = int(item.get("location_id") or 0)
    for _ in range(25):
        parent = by_item.get(location)
        if parent is None:
            return location
        location = int(parent.get("location_id") or 0)
    return location


def aggregate_assets(assets: list, relevant: set) -> dict:
    """{(type_id, root location): quantity} for the types we know."""
    by_item = {int(a["item_id"]): a for a in assets if a.get("item_id") is not None}
    totals = collections.Counter()
    for asset in assets:
        type_id = int(asset.get("type_id") or 0)
        if type_id not in relevant:
            continue
        totals[(type_id, root_location(asset, by_item))] += int(asset.get("quantity") or 0)
    return totals


@transaction.atomic
def _store_assets(user, character_id: int, assets: list) -> int:
    CharacterAsset.objects.filter(character_id=character_id).delete()
    totals = aggregate_assets(assets, relevant_type_ids())
    rows = [
        CharacterAsset(user=user, character_id=character_id, type_id=type_id, location_id=location, quantity=quantity)
        for (type_id, location), quantity in totals.items()
        if quantity > 0
    ]
    CharacterAsset.objects.bulk_create(rows)
    return len(rows)


# --- names ---------------------------------------------------------------------

def ensure_type_names(type_ids) -> None:
    ids = {int(t) for t in type_ids if t}
    missing = ids - set(MaterialType.objects.filter(type_id__in=ids).values_list("type_id", flat=True))
    if not missing:
        return
    try:
        from eveuniverse.models import EveEntity

        resolver = EveEntity.objects.bulk_resolve_names(missing)
        for type_id in missing:
            name = resolver.to_name(type_id)
            if name:
                MaterialType.objects.update_or_create(type_id=type_id, defaults={"name": name})
    except Exception as exc:  # noqa: BLE001
        logger.warning("type names not resolved: %s", exc)


def ensure_location_names(location_ids, access_token: str) -> None:
    ids = {int(i) for i in location_ids if i}
    if not ids:
        return
    known = {}
    for row in LocationName.objects.filter(location_id__in=ids):
        known[row.location_id] = row
    retry_after = timezone.now() - dt.timedelta(days=1)
    todo = {
        i for i in ids
        if i not in known or (known[i].kind == "unknown" and known[i].fetched_at < retry_after)
    }
    if not todo:
        return
    try:
        from eveuniverse.models import EveEntity
    except Exception:  # noqa: BLE001
        EveEntity = None
    public = {i for i in todo if i < STRUCTURE_MIN}
    names = {}
    if public and EveEntity is not None:
        try:
            resolver = EveEntity.objects.bulk_resolve_names(public)
            names = {i: resolver.to_name(i) for i in public}
        except Exception as exc:  # noqa: BLE001
            logger.warning("location names not resolved: %s", exc)
    for location_id in sorted(todo):
        name, system, kind = "", "", "unknown"
        if location_id >= STRUCTURE_MIN:
            try:
                info = esi.structure_info(location_id, access_token)
                name = info.get("name") or ""
                kind = "structure"
                if EveEntity is not None and info.get("solar_system_id"):
                    system = EveEntity.objects.resolve_name(int(info["solar_system_id"])) or ""
            except Exception as exc:  # noqa: BLE001
                logger.info("structure %s not readable with this character: %s", location_id, exc)
        else:
            name = names.get(location_id) or ""
            if name:
                kind = "station" if STATION_RANGE[0] <= location_id < STATION_RANGE[1] else "place"
        LocationName.objects.update_or_create(
            location_id=location_id,
            defaults={"name": name or f"Location {location_id}", "system_name": system, "kind": kind, "fetched_at": timezone.now()},
        )


# --- who sees whom -----------------------------------------------------------------

def allowed_scopes(user) -> list[str]:
    scopes = ["own"]
    if user.has_perm("shipyard.view_corp_industry") or user.has_perm("shipyard.view_alliance_industry"):
        scopes.append("corp")
    if user.has_perm("shipyard.view_alliance_industry"):
        scopes.append("alliance")
    return scopes


def visible_syncs(user, scope: str):
    """The synced characters a member may look at in this scope."""
    if scope == "own":
        return CharacterSync.objects.filter(user=user).order_by("character_name")
    main = getattr(getattr(user, "profile", None), "main_character", None)
    if main is None:
        return CharacterSync.objects.filter(user=user).order_by("character_name")
    if scope == "alliance" and main.alliance_id:
        ids = EveCharacter.objects.filter(alliance_id=main.alliance_id).values_list("character_id", flat=True)
    else:
        ids = EveCharacter.objects.filter(corporation_id=main.corporation_id).values_list("character_id", flat=True)
    return CharacterSync.objects.filter(character_id__in=list(ids)).order_by("character_name")


# --- what the pages show -----------------------------------------------------------

def owned_blueprints(user) -> dict:
    """Best blueprint per blueprint type the member owns: {type_id: {me, te, kind, character_name, runs}}.

    An original beats a copy; then the higher ME, then the higher TE.
    """
    syncs = {s.character_id: s.character_name for s in CharacterSync.objects.filter(user=user)}
    best = {}
    for bp in CharacterBlueprint.objects.filter(user=user):
        original = bp.quantity != -2
        key = (original, bp.me, bp.te)
        current = best.get(bp.type_id)
        if current is None or key > current["_key"]:
            best[bp.type_id] = {
                "_key": key, "me": bp.me, "te": bp.te, "kind": "BPO" if original else "BPC",
                "runs": bp.runs, "character_name": syncs.get(bp.character_id, ""),
            }
    for row in best.values():
        row.pop("_key", None)
    return best


def overview(user, scope: str = "own") -> dict:
    now = timezone.now()
    names = {}

    def name_of(type_id):
        if type_id is None:
            return "–"
        if type_id not in names:
            names[type_id] = MaterialType.objects.filter(type_id=type_id).values_list("name", flat=True).first() or f"Type {type_id}"
        return names[type_id]

    locations = {l.location_id: l for l in LocationName.objects.all()}

    def place(location_id):
        loc = locations.get(location_id)
        if loc is None:
            return f"Location {location_id}", ""
        return loc.name, loc.system_name

    syncs = list(visible_syncs(user, scope))
    character_ids = [s.character_id for s in syncs]
    character_names = {s.character_id: s.character_name for s in syncs}
    jobs = list(IndustryJob.objects.filter(character_id__in=character_ids).order_by("end_date"))
    ships_by_type = {s.type_id: s for s in Ship.objects.all()}
    ships_by_blueprint = {s.blueprint_type_id: s for s in Ship.objects.all()}

    active, ready, recent = [], [], []
    used = collections.Counter()
    for job in jobs:
        kind = "manufacturing" if job.activity_id in constants.MANUFACTURING_ACTIVITIES else "science"
        row = {
            "job": job,
            "activity": constants.ACTIVITIES.get(job.activity_id, f"Activity {job.activity_id}"),
            "product": name_of(job.product_type_id or job.blueprint_type_id),
            "product_type_id": job.product_type_id or job.blueprint_type_id,
            "ship": ships_by_type.get(job.product_type_id),
            "place": place(job.location_id),
            "remaining": (job.end_date - now) if job.end_date else None,
            "kind": kind,
        }
        # EVE keeps a finished job "active" until it is delivered: the end date decides
        finished = job.end_date is not None and job.end_date <= now
        if job.status == READY_STATUS or (job.status in ACTIVE_STATUSES and finished):
            ready.append(row)
            used[(job.character_id, kind)] += 1
        elif job.status in ACTIVE_STATUSES:
            active.append(row)
            used[(job.character_id, kind)] += 1
        elif job.status == "delivered" and job.end_date and now - job.end_date <= dt.timedelta(days=RECENT_DAYS):
            recent.append(row)
    recent.sort(key=lambda r: r["job"].end_date, reverse=True)

    slots = [
        {
            "sync": s,
            "manufacturing_used": used[(s.character_id, "manufacturing")],
            "science_used": used[(s.character_id, "science")],
        }
        for s in syncs
    ]

    blueprints = []
    for bp in CharacterBlueprint.objects.filter(character_id__in=character_ids).order_by("type_id"):
        blueprints.append({
            "bp": bp,
            "name": name_of(bp.type_id),
            "kind": "BPO" if bp.quantity != -2 else "BPC",
            "stack": bp.quantity if bp.quantity > 0 else 1,
            "place": place(bp.location_id),
            "character_name": character_names.get(bp.character_id, ""),
            "ship": ships_by_blueprint.get(bp.type_id),
        })
    blueprints.sort(key=lambda r: (r["ship"] is None, r["name"]))

    market = MarketLocation.objects.filter(is_default=True, is_active=True).first()
    prices = {}
    if market:
        prices = dict(PriceSnapshot.objects.filter(location=market).values_list("type_id", "sell_min"))
    material_ids = set()
    for mats in BuildSnapshot.objects.values_list("materials", flat=True):
        material_ids.update(int(m["type_id"]) for m in mats)
    by_place = collections.defaultdict(lambda: {"materials": [], "ships": [], "value": 0.0})
    for asset in CharacterAsset.objects.filter(character_id__in=character_ids).order_by("location_id", "type_id"):
        unit = prices.get(asset.type_id)
        value = (unit or 0.0) * asset.quantity
        row = {
            "type_id": asset.type_id, "name": name_of(asset.type_id), "quantity": asset.quantity,
            "unit_price": unit, "value": value, "character_name": character_names.get(asset.character_id, ""),
        }
        bucket = by_place[asset.location_id]
        bucket["value"] += value
        if asset.type_id in ships_by_type:
            row["ship"] = ships_by_type[asset.type_id]
            bucket["ships"].append(row)
        elif asset.type_id in material_ids:
            bucket["materials"].append(row)
    stock = []
    for location_id, bucket in by_place.items():
        if not bucket["materials"] and not bucket["ships"]:
            continue
        name, system = place(location_id)
        bucket["materials"].sort(key=lambda r: -r["value"])
        bucket["ships"].sort(key=lambda r: -r["value"])
        stock.append({"location_id": location_id, "name": name, "system": system, **bucket})
    stock.sort(key=lambda s: -s["value"])

    return {
        "scope": scope,
        "scopes": allowed_scopes(user),
        "syncs": syncs,
        "slots": slots,
        "active_jobs": active,
        "ready_jobs": ready,
        "recent_jobs": recent,
        "blueprints": blueprints,
        "stock": stock,
        "stock_value": sum(s["value"] for s in stock),
        "market": market,
        "has_characters": bool(syncs),
        "own_characters": CharacterSync.objects.filter(user=user).exists(),
    }
