"""ESI calls (public history and indices; authed skills)."""

import logging

from .. import constants
from .http import get_json, session

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"


def market_history(region_id: int, type_id: int) -> list[dict]:
    return get_json(f"{ESI}/markets/{int(region_id)}/history/", params={"datasource": "tranquility", "type_id": int(type_id)})


def buy_orders(region_id: int, type_id: int, max_pages: int = 10) -> list[dict]:
    """Every open buy order for one type in a region (public, paged)."""
    params = {"datasource": "tranquility", "order_type": "buy", "type_id": int(type_id)}
    url = f"{ESI}/markets/{int(region_id)}/orders/"
    first = session().get(url, params={**params, "page": 1}, timeout=30)
    first.raise_for_status()
    orders = list(first.json() or [])
    pages = min(int(first.headers.get("X-Pages") or 1), max_pages)
    for page in range(2, pages + 1):
        r = session().get(url, params={**params, "page": page}, timeout=30)
        r.raise_for_status()
        orders.extend(r.json() or [])
    return orders


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


def character_standings(character_id: int, access_token: str) -> dict[str, float]:
    """{entity id (as text): unmodified standing} for every NPC the character has standing with."""
    r = session().get(
        f"{ESI}/characters/{int(character_id)}/standings/",
        params={"datasource": "tranquility"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    r.raise_for_status()
    return {str(int(s["from_id"])): float(s.get("standing") or 0) for s in r.json() or []}


def _authed(path: str, access_token: str, params=None):
    r = session().get(
        f"{ESI}{path}",
        params={"datasource": "tranquility", **(params or {})},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r


def _authed_pages(path: str, access_token: str, max_pages: int = 20) -> list:
    """All pages of a paged ESI list (X-Pages), capped."""
    first = _authed(path, access_token, {"page": 1})
    rows = list(first.json() or [])
    pages = min(int(first.headers.get("X-Pages") or 1), max_pages)
    for page in range(2, pages + 1):
        rows.extend(_authed(path, access_token, {"page": page}).json() or [])
    return rows


def character_skill_levels(character_id: int, access_token: str, skill_ids) -> dict[int, int]:
    """{skill_id: active level} for the given skills."""
    wanted = {int(s) for s in skill_ids}
    levels = {}
    for s in _authed(f"/characters/{int(character_id)}/skills/", access_token).json().get("skills") or []:
        sid = int(s.get("skill_id"))
        if sid in wanted:
            levels[sid] = int(s.get("active_skill_level") or 0)
    return levels


def character_skills(character_id: int, access_token: str) -> dict[int, int]:
    """{skill_id: active level} for the skills the calculation cares about."""
    return character_skill_levels(character_id, access_token, constants.RELEVANT_SKILLS)


def character_industry_jobs(character_id: int, access_token: str) -> list[dict]:
    return list(_authed(f"/characters/{int(character_id)}/industry/jobs/", access_token, {"include_completed": "true"}).json() or [])


def character_blueprints(character_id: int, access_token: str) -> list[dict]:
    return _authed_pages(f"/characters/{int(character_id)}/blueprints/", access_token)


def character_assets(character_id: int, access_token: str, max_pages: int = 20) -> list[dict]:
    return _authed_pages(f"/characters/{int(character_id)}/assets/", access_token, max_pages=max_pages)


def structure_info(structure_id: int, access_token: str) -> dict:
    """Name and system of an Upwell structure the character may dock at."""
    return _authed(f"/universe/structures/{int(structure_id)}/", access_token).json() or {}
