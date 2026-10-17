"""The skills check: what a fit requires, what the member's character has, and the gap.

Requirements come from EVE's dogma attributes on every type in the fit (requiredSkill1..6 and
their levels), stored on ItemType by types.fetch_type(). A required skill's own prerequisites
count too (a skill type carries the same attributes), so the check matches the game's "can fly".
The character's skills come from ESI (esi-skills.read_skills.v1) through a django-esi token of the
member's own character, kept in MemberCharacter and refreshed when older than MAX_AGE.
"""

import datetime as dt
import logging

from django.utils import timezone
from esi.models import Token

from ..models import ItemType, MemberCharacter
from . import ESI_BASE, session
from . import types as types_service

logger = logging.getLogger(__name__)

SCOPE = "esi-skills.read_skills.v1"
SCOPES = [SCOPE]
MAX_AGE = dt.timedelta(hours=12)
LEVELS = {0: "0", 1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
MAX_LAZY_FETCHES = 40  # types looked up from EVE during one page view when the table lacks them


def roman(level) -> str:
    return LEVELS.get(int(level or 0), str(level))


# ---- requirements ----------------------------------------------------------------------------

def _type_rows(type_ids) -> dict[int, ItemType]:
    rows = {t.type_id: t for t in ItemType.objects.filter(type_id__in=list(type_ids))}
    budget = MAX_LAZY_FETCHES
    for tid in type_ids:
        row = rows.get(tid)
        if (row is None or row.skills_fetched_at is None) and budget > 0:
            budget -= 1
            fetched = types_service.fetch_type(tid, row.name if row else "")
            if fetched:
                rows[tid] = fetched
    return rows


def requirements(type_ids, item_names=None) -> dict[int, dict]:
    """{skill_id: {"level": highest level any item needs, "for": [item names]}} for the types of a fit,
    prerequisites of the required skills included (at the prerequisite's level)."""
    item_names = item_names or {}
    out: dict[int, dict] = {}
    rows = _type_rows(set(int(t) for t in type_ids))
    queue = []
    for tid, row in rows.items():
        for skill_id, level in row.required_skills or []:
            queue.append((int(skill_id), int(level), item_names.get(tid) or row.name))
    seen_pairs = set()
    while queue:
        skill_id, level, because = queue.pop()
        entry = out.setdefault(skill_id, {"level": 0, "for": []})
        if level > entry["level"]:
            entry["level"] = level
        if because and because not in entry["for"]:
            entry["for"].append(because)
        if (skill_id, level) in seen_pairs:
            continue
        seen_pairs.add((skill_id, level))
        skill_rows = _type_rows({skill_id})
        skill_row = skill_rows.get(skill_id)
        if skill_row is None:
            continue
        for pre_id, pre_level in skill_row.required_skills or []:
            queue.append((int(pre_id), int(pre_level), skill_row.name))
    return out


def check(type_ids, have: dict, item_names=None) -> dict:
    """Compare a fit's requirements with {skill_id: level}: the missing skills (highest need first),
    how many requirements there are in all, and whether everything is trained."""
    reqs = requirements(type_ids, item_names)
    names = {t.type_id: t.name for t in ItemType.objects.filter(type_id__in=list(reqs))}
    missing = []
    for skill_id, entry in reqs.items():
        own = int(have.get(skill_id, have.get(str(skill_id), 0)) or 0)
        if own < entry["level"]:
            missing.append({
                "skill_id": skill_id, "name": names.get(skill_id) or f"skill {skill_id}",
                "need": entry["level"], "have": own, "need_roman": roman(entry["level"]), "have_roman": roman(own),
                "for": entry["for"][:6], "gap": entry["level"] - own,
            })
    missing.sort(key=lambda m: (-m["gap"], m["name"]))
    return {"missing": missing, "total": len(reqs), "ok": not missing, "count": len(missing)}


# ---- the member's character ------------------------------------------------------------------

def token_for(user, character_id: int):
    """A valid token of this user for this character that carries the skills scope, or None."""
    return Token.objects.filter(user=user, character_id=int(character_id)).require_scopes(SCOPES).require_valid().first()


def esi_skills(character_id: int, access_token: str) -> tuple[dict, int]:
    """({skill_id: active level}, total skill points) from ESI."""
    r = session().get(
        f"{ESI_BASE}/characters/{int(character_id)}/skills/",
        params={"datasource": "tranquility"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json() or {}
    levels = {str(int(s["skill_id"])): int(s.get("active_skill_level") or 0) for s in data.get("skills") or []}
    return levels, int(data.get("total_sp") or 0)


def load(user, token) -> MemberCharacter:
    """Read the token's character from ESI into the member's MemberCharacter row (created or replaced)."""
    levels, total_sp = esi_skills(token.character_id, token.valid_access_token())
    mc, _ = MemberCharacter.objects.update_or_create(
        user=user,
        defaults={
            "character_id": token.character_id, "character_name": token.character_name,
            "skills": levels, "total_sp": total_sp, "fetched_at": timezone.now(),
        },
    )
    return mc


def current(user):
    try:
        return user.doctrines_character
    except MemberCharacter.DoesNotExist:
        return None


def ensure_fresh(mc: MemberCharacter) -> MemberCharacter:
    """Refresh a stale row when a token still exists; a failure keeps the old skills."""
    if mc is None:
        return None
    if mc.fetched_at and timezone.now() - mc.fetched_at < MAX_AGE:
        return mc
    token = token_for(mc.user, mc.character_id)
    if token is None:
        return mc
    try:
        return load(mc.user, token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("skills of %s not refreshed: %s", mc.character_name, exc)
        return mc


def choices(user, mc=None) -> list[dict]:
    """The characters on the member's auth account, for the switch."""
    rows = []
    for ownership in user.character_ownerships.select_related("character").order_by("character__character_name"):
        character = ownership.character
        rows.append({
            "character": character,
            "in_use": mc is not None and character.character_id == mc.character_id,
            "has_token": token_for(user, character.character_id) is not None,
        })
    return rows
