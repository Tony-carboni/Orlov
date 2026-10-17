"""EVE types for the fittings: names to ids (ESI /universe/ids/), and the slot of every type from its
dogma effects (ESI /universe/types/{id}/), cached in ItemType so each type is looked up once."""

import logging

from django.utils import timezone

from ..models import ItemType
from . import get_json, polite_pause, post_json

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"
# dogma effects that place a module: loPower 11, hiPower 12, medPower 13, rigSlot 2663, subSystem 3772
SLOT_EFFECTS = {11: "low", 12: "high", 13: "mid", 2663: "rig", 3772: "subsystem"}
CATEGORY_SHIP = 6
CATEGORY_CHARGE = 8
CATEGORY_DRONE = 18
CATEGORY_IMPLANT = 20
CATEGORY_FIGHTER = 87


def slot_of(type_info: dict) -> str:
    """The slot from a type's category and dogma effects. Pure."""
    category = int(type_info.get("category_id") or 0)
    if category == CATEGORY_SHIP:
        return "ship"
    if category == CATEGORY_DRONE or category == CATEGORY_FIGHTER:
        return "drone"
    if category == CATEGORY_CHARGE:
        return "charge"
    if category == CATEGORY_IMPLANT:
        return "implant"
    for e in type_info.get("dogma_effects") or []:
        slot = SLOT_EFFECTS.get(int(e.get("effect_id") or 0))
        if slot:
            return slot
    return "cargo"


def resolve_names(names: list[str]) -> dict:
    """{lower-cased name: ItemType} for every name that EVE knows as an inventory type; fetches the unknown ones."""
    wanted = {n.strip() for n in names if n and n.strip()}
    known = {t.name.lower(): t for t in ItemType.objects.filter(name__in=wanted)}
    missing = [n for n in wanted if n.lower() not in known]
    if missing:
        for i in range(0, len(missing), 100):
            chunk = missing[i:i + 100]
            try:
                data = post_json(f"{ESI}/universe/ids/", chunk, params={"datasource": "tranquility"})
            except Exception as exc:  # noqa: BLE001
                logger.warning("names not resolved: %s", exc)
                data = {}
            for row in data.get("inventory_types") or []:
                t = fetch_type(int(row["id"]), row.get("name") or "")
                if t:
                    known[t.name.lower()] = t
            polite_pause()
    return known


def fetch_type(type_id: int, name: str = "") -> ItemType | None:
    """Read one type from ESI (group, category, dogma effects) and store it; None when ESI has no such type."""
    try:
        info = get_json(f"{ESI}/universe/types/{int(type_id)}/", params={"datasource": "tranquility"})
    except Exception as exc:  # noqa: BLE001
        logger.warning("type %s not read: %s", type_id, exc)
        return None
    group_id = int(info.get("group_id") or 0)
    category_id = 0
    try:
        category_id = int(get_json(f"{ESI}/universe/groups/{group_id}/", params={"datasource": "tranquility"}).get("category_id") or 0)
    except Exception as exc:  # noqa: BLE001
        logger.info("group %s not read: %s", group_id, exc)
    info["category_id"] = category_id
    t, _ = ItemType.objects.update_or_create(
        type_id=int(type_id),
        defaults={
            "name": info.get("name") or name, "group_id": group_id, "category_id": category_id,
            "slot": slot_of(info), "volume": float(info.get("packaged_volume") or info.get("volume") or 0),
            "fetched_at": timezone.now(),
        },
    )
    return t


def as_map(types: dict) -> dict:
    """ItemType rows → the plain dicts the parser's layout() wants."""
    return {k: {"type_id": t.type_id, "name": t.name, "slot": t.slot, "volume": t.volume} for k, t in types.items()}
