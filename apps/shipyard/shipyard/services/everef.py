"""EVE Ref: reference data and the industry cost API."""

import logging
import re

from .http import get_json

logger = logging.getLogger(__name__)

REF_BASE = "https://ref-data.everef.net"
COST_URL = "https://api.everef.net/v1/industry/cost"


def get_type(type_id: int) -> dict:
    return get_json(f"{REF_BASE}/types/{int(type_id)}")


def get_group(group_id: int) -> dict:
    return get_json(f"{REF_BASE}/groups/{int(group_id)}")


def get_category(category_id: int) -> dict:
    return get_json(f"{REF_BASE}/categories/{int(category_id)}")


def type_name(data: dict) -> str:
    name = data.get("name") or {}
    if isinstance(name, dict):
        return name.get("en") or next(iter(name.values()), "")
    return str(name)


_DURATION = re.compile(r"P(?:(?P<d>\d+)D)?T?(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>[\d.]+)S)?")


def parse_duration(iso: str) -> int:
    """ISO-8601 duration (PT2H18M43S) → seconds."""
    if not iso:
        return 0
    m = _DURATION.fullmatch(iso)
    if not m:
        return 0
    d = int(m.group("d") or 0)
    h = int(m.group("h") or 0)
    mi = int(m.group("m") or 0)
    s = float(m.group("s") or 0)
    return int(d * 86400 + h * 3600 + mi * 60 + s)


def manufacturing_cost(
    product_id: int,
    *,
    system_id: int,
    structure_type_id: int | None,
    rig_type_ids=(),
    facility_tax_pct: float = 0,
    me: int = 0,
    te: int = 0,
    runs: int = 1,
    skills: dict | None = None,
) -> dict:
    """Return the `manufacturing.<product_id>` block of the EVE Ref cost API.

    Quantities already include ME, structure and rig bonuses. Material prices
    in the response are ignored by us (we price with our own market snapshot).
    """
    params = [
        ("product_id", int(product_id)),
        ("runs", int(runs)),
        ("me", int(me)),
        ("te", int(te)),
        ("system_id", int(system_id)),
        ("facility_tax", float(facility_tax_pct) / 100.0),
    ]
    if structure_type_id:
        params.append(("structure_type_id", int(structure_type_id)))
    for rig in rig_type_ids or ():
        params.append(("rig_id", int(rig)))
    for key, value in (skills or {}).items():
        params.append((key, int(value)))
    data = get_json(COST_URL, params=params)
    block = (data.get("manufacturing") or {}).get(str(int(product_id)))
    if not block:
        raise ValueError(f"EVE Ref returned no manufacturing block for {product_id}: {str(data)[:200]}")
    return block


def normalise_cost_block(block: dict) -> dict:
    """Pick the fields we store from a cost block."""
    materials = []
    for type_id, m in (block.get("materials") or {}).items():
        materials.append({"type_id": int(type_id), "quantity": float(m.get("quantity") or 0)})
    materials.sort(key=lambda x: -x["quantity"])
    return {
        "materials": materials,
        "estimated_item_value": float(block.get("estimated_item_value") or 0),
        "job_cost": float(block.get("total_job_cost") or 0),
        "system_cost_isk": float(block.get("system_cost_index") or 0),
        "scc_surcharge": float(block.get("scc_surcharge") or 0),
        "facility_tax_isk": float(block.get("facility_tax") or 0),
        "time_seconds": parse_duration(block.get("time_per_run") or block.get("time") or ""),
        "materials_volume": float(block.get("materials_volume") or 0),
    }
