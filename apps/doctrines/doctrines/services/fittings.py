"""Fittings: parse the pasted text once on save (resolving every item to an EVE type) and store the
result on the DoctrineShip; and build what the doctrine page shows per ship (slots, cost, insurance)."""

import logging

from .. import app_settings
from ..models import DoctrineShip
from . import eft, insurance, prices, types

logger = logging.getLogger(__name__)


def store(ship: DoctrineShip) -> DoctrineShip:
    """Parse ship.fitting_text, resolve the names, fill ship_type_id/name, fitting_json and parse_error. Saves nothing."""
    ship.parse_error = ""
    try:
        parsed = eft.parse(ship.fitting_text)
    except eft.FittingError as exc:
        ship.parse_error = str(exc)
        ship.fitting_json = {}
        return ship
    known = types.as_map(types.resolve_names(eft.names_in(parsed)))
    data = eft.layout(parsed, known)
    hull = data["hull"]
    if hull is None:
        ship.parse_error = f"EVE does not know a ship called '{parsed['hull']}'"
        ship.fitting_json = {}
        return ship
    ship.ship_type_id = hull["type_id"]
    ship.ship_type_name = hull["name"]
    if not ship.name:
        ship.name = f"{parsed['hull']}, {parsed['name']}"
    ship.fitting_json = {
        "hull": hull, "name": parsed["name"], "slots": data["slots"], "unknown": data["unknown"],
        "text": eft.eft_text(parsed),
    }
    if data["unknown"]:
        ship.parse_error = "EVE does not know: " + ", ".join(data["unknown"][:5]) + (" …" if len(data["unknown"]) > 5 else "")
    return ship


def type_ids_of(ship: DoctrineShip) -> set[int]:
    ids = {ship.ship_type_id} if ship.ship_type_id else set()
    for rows in (ship.fitting_json or {}).get("slots", {}).values():
        for r in rows:
            ids.add(int(r["type_id"]))
            if r.get("charge"):
                ids.add(int(r["charge"]["type_id"]))
    return ids


def page_data(ships, srp_percent: int = 0) -> list[dict]:
    """For the doctrine page: one dict per ship with the layout, cost, insurance and SRP.
    srp_percent: the doctrine's ship replacement as a share of the cost; it comes off the loss."""
    ships = list(ships)
    ids = set()
    for s in ships:
        ids |= type_ids_of(s)
    price = prices.price_map(ids)
    ins = insurance.net_map({s.ship_type_id for s in ships if s.ship_type_id})
    out = []
    for s in ships:
        fj = s.fitting_json or {}
        layout = {"hull": fj.get("hull"), "slots": fj.get("slots") or {k: [] for k in eft.SLOT_ORDER}, "unknown": fj.get("unknown") or []}
        c = eft.cost(layout, price) if fj else {"hull": 0, "fit": 0, "drones": 0, "cargo": 0, "total": 0, "missing": []}
        cost_, payout, net = ins.get(s.ship_type_id, (None, None, None))
        pct = s.srp_percent if s.srp_percent is not None else srp_percent
        srp = c["total"] * pct / 100.0 if (pct and c["total"]) else 0.0
        groups = [{"slot": slot, "label": eft.SLOT_LABELS[slot], "rows": layout["slots"].get(slot, [])} for slot in eft.SLOT_ORDER if layout["slots"].get(slot)]
        out.append({
            "ship": s, "layout": layout, "groups": groups, "cost": c,
            "insurance": {"cost": cost_, "payout": payout, "net": net},
            "srp": srp, "srp_percent": pct,
            "loss": (c["total"] - net - srp) if (net is not None and c["total"]) else None,
            "text": fj.get("text") or s.fitting_text,
        })
    return out


def grouped(rows: list[dict]) -> list[dict]:
    """The doctrine page's overview: one entry per hull and role, its fits (T1, T2, ...) as variants in
    the order of the ships. A ship without a variant is a group of one. The hull is named by EVE
    (ship_type_name) and falls back to the fit's name when the fitting did not parse."""
    groups = []
    index = {}
    for r in rows:
        s = r["ship"]
        key = (s.ship_type_id or s.name.lower(), s.role.strip().lower())
        g = index.get(key)
        if g is None:
            g = {
                "key": f"{s.ship_type_id or 0}-{len(groups)}", "ship": s, "type_id": s.ship_type_id,
                "hull": s.ship_type_name or s.name, "role": s.role, "variants": [],
            }
            index[key] = g
            groups.append(g)
        r["label"] = s.variant or (s.name if len(g["variants"]) else "")
        g["variants"].append(r)
    for g in groups:
        if len(g["variants"]) > 1 and not g["variants"][0]["label"]:
            g["variants"][0]["label"] = g["variants"][0]["ship"].name
        g["multi"] = len(g["variants"]) > 1
        g["srp_levels"] = []
        for r in g["variants"]:
            lvl = r["ship"].srp_level
            if lvl and lvl not in g["srp_levels"]:
                g["srp_levels"].append(lvl)
        g["notes"] = [r["ship"].notes for r in g["variants"] if r["ship"].notes]
        g["errors"] = [r["ship"].parse_error for r in g["variants"] if r["ship"].parse_error]
    return groups


ROLE_ICONS = {
    "dps": "fa-crosshairs", "logi": "fa-kit-medical", "logistics": "fa-kit-medical", "tackle": "fa-link",
    "support": "fa-satellite-dish", "ewar": "fa-satellite-dish", "boosts": "fa-wave-square", "scout": "fa-eye",
    "fc": "fa-flag", "command": "fa-flag",
}


def by_role(groups: list[dict]) -> list[dict]:
    """The hull groups under role headers (DPS, Logi, Tackle, ...), in the order the roles first appear."""
    out = []
    index = {}
    for g in groups:
        key = g["role"].strip().lower()
        block = index.get(key)
        if block is None:
            block = {"role": g["role"].strip(), "icon": ROLE_ICONS.get(key, "fa-user-group"), "hulls": []}
            index[key] = block
            out.append(block)
        block["hulls"].append(g)
    return out


def market_name() -> str:
    return app_settings.DOCTRINES_MARKET_NAME
