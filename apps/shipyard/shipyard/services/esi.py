"""ESI calls (public history and indices; authed skills)."""

import logging

from .. import constants
from .http import get_json, session

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"


def market_history(region_id: int, type_id: int) -> list[dict]:
    return get_json(f"{ESI}/markets/{int(region_id)}/history/", params={"datasource": "tranquility", "type_id": int(type_id)})


def volume_stats(region_id: int, type_id: int, days: int) -> dict:
    """Average daily volume and average price over the last `days` entries."""
    hist = market_history(region_id, type_id)
    tail = hist[-days:] if hist else []
    if not tail:
        return {"avg_daily_volume": 0.0, "avg_price": 0.0, "days": days}
    # Days without trades are missing from history; divide by the window, not the rows.
    vol = sum(float(h.get("volume") or 0) for h in tail) / float(days)
    price = sum(float(h.get("average") or 0) for h in tail) / len(tail)
    return {"avg_daily_volume": vol, "avg_price": price, "days": days}


def industry_indices() -> dict[int, float]:
    """{system_id: manufacturing cost index}."""
    data = get_json(f"{ESI}/industry/systems/", params={"datasource": "tranquility"})
    out = {}
    for row in data:
        for ci in row.get("cost_indices") or []:
            if ci.get("activity") == "manufacturing":
                out[int(row["solar_system_id"])] = float(ci.get("cost_index") or 0)
    return out


def character_skills(character_id: int, access_token: str) -> dict[int, int]:
    """{skill_id: active level} for the skills we care about."""
    r = session().get(
        f"{ESI}/characters/{int(character_id)}/skills/",
        params={"datasource": "tranquility"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    r.raise_for_status()
    levels = {}
    for s in r.json().get("skills") or []:
        sid = int(s.get("skill_id"))
        if sid in constants.RELEVANT_SKILLS:
            levels[sid] = int(s.get("active_skill_level") or 0)
    return levels
