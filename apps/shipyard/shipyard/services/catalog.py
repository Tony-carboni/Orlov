"""Build and classify the ship catalog from EVE Ref reference data."""

import logging

from .. import constants
from . import everef
from .http import polite_pause

logger = logging.getLogger(__name__)


def classify(type_data: dict) -> dict | None:
    """Return the Ship fields for a type, or None if it is not a buildable T1/faction hull."""
    if not type_data.get("published"):
        return None
    group_id = int(type_data.get("group_id") or 0)
    hull = constants.HULL_GROUPS.get(group_id)
    if not hull:
        return None
    blueprints = type_data.get("produced_by_blueprints") or {}
    manufacturing = [int(k) for k, v in blueprints.items() if (v or {}).get("blueprint_activity") == "manufacturing"]
    if not manufacturing:
        return None
    meta = type_data.get("meta_group_id")
    meta = int(meta) if meta is not None else constants.META_TECH_I  # old hulls carry no meta group
    if meta not in (constants.META_TECH_I, constants.META_FACTION):
        return None
    faction_id = type_data.get("faction_id")
    faction_id = int(faction_id) if faction_id else None

    if faction_id in constants.TRIG_FACTION:
        category = constants.CAT_TRIG
    elif faction_id in constants.EDENCOM_FACTION:
        category = constants.CAT_EDENCOM
    elif faction_id in constants.PIRATE_FACTIONS:
        category = constants.CAT_PIRATE
    elif faction_id in constants.ORE_FACTION:
        category = constants.CAT_ORE if meta == constants.META_FACTION else constants.CAT_BASE
    elif faction_id in constants.EMPIRE_FACTIONS:
        category = constants.CAT_NAVY if meta == constants.META_FACTION else constants.CAT_BASE
    else:
        category = constants.CAT_OTHER

    name = everef.type_name(type_data)
    return {
        "type_id": int(type_data["type_id"]),
        "name": name,
        "group_id": group_id,
        "hull_size": hull,
        "category": category,
        "faction_id": faction_id,
        "faction_name": constants.FACTION_NAMES.get(faction_id, ""),
        "meta_group_id": meta,
        "blueprint_type_id": min(manufacturing),
        "volume": float(type_data.get("packaged_volume") or type_data.get("volume") or 0),
        "default_active": (
            name not in constants.INACTIVE_BY_DEFAULT and category != constants.CAT_OTHER
        ),
    }


def iter_catalog():
    """Yield classified ship dicts for every type in the hull groups."""
    for group_id in constants.HULL_GROUPS:
        group = everef.get_group(group_id)
        for type_id in group.get("type_ids") or []:
            try:
                data = everef.get_type(type_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("EVE Ref type %s failed: %s", type_id, exc)
                continue
            row = classify(data)
            if row:
                yield row
            polite_pause()
