"""The fitting text as the game exports it (EFT format), parsed into lines. Pure: no EVE, no database.

The game's export looks like this:

    [Harpy, Rail Harpy v3]
    Magnetic Field Stabilizer II
    ...
    (blank line between slot groups)
    150mm Railgun II, Spike S
    ...
    Hobgoblin II x2
    ...
    Spike S x1000

Rules used here:
- the first non-empty line is "[Hull, Fit name]";
- a line "Name, Charge" is a module with a charge loaded;
- a line "Name xN" is N of that item (drones, cargo);
- "[Empty High slot]" and the like are skipped;
- blank lines separate groups but are not relied on: the slot of every item comes from its EVE type
  (services/types.py), so a fitting pasted without the blank lines parses just the same.
"""

import re
from collections import OrderedDict

HEADER = re.compile(r"^\[(?P<hull>[^,\]]+)\s*,\s*(?P<name>[^\]]*)\]\s*$")
EMPTY = re.compile(r"^\[empty .* slot\]$", re.I)
QUANTITY = re.compile(r"^(?P<name>.+?)\s+x(?P<qty>\d+)\s*$", re.I)


class FittingError(ValueError):
    pass


def parse(text: str) -> dict:
    """{'hull': 'Harpy', 'name': 'Rail Harpy v3', 'items': [{'name', 'quantity', 'charge'}]}
    Items keep the order of the text; the same name on several lines stays on several lines."""
    lines = [ln.strip() for ln in (text or "").replace("\r", "").split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines:
        raise FittingError("the fitting is empty")
    m = HEADER.match(lines[0])
    if not m:
        raise FittingError("the first line must be [Hull, Fit name], as the game exports it")
    items = []
    for ln in lines[1:]:
        if EMPTY.match(ln):
            continue
        charge = None
        name = ln
        quantity = 1
        q = QUANTITY.match(name)
        if q:
            name, quantity = q.group("name").strip(), int(q.group("qty"))
        elif "," in name:
            # "Module, Charge" (a charge name never contains a comma, a module name may not either)
            left, right = name.rsplit(",", 1)
            if right.strip():
                name, charge = left.strip(), right.strip()
        items.append({"name": name, "quantity": quantity, "charge": charge})
    return {"hull": m.group("hull").strip(), "name": m.group("name").strip() or m.group("hull").strip(), "items": items}


def names_in(parsed: dict) -> list[str]:
    """Every distinct name the fitting mentions, hull first, charges included."""
    out = OrderedDict()
    out[parsed["hull"]] = None
    for it in parsed["items"]:
        out[it["name"]] = None
        if it.get("charge"):
            out[it["charge"]] = None
    return list(out)


SLOT_ORDER = ["high", "mid", "low", "rig", "subsystem", "drone", "charge", "implant", "cargo"]
SLOT_LABELS = {
    "high": "High slots", "mid": "Mid slots", "low": "Low slots", "rig": "Rigs", "subsystem": "Subsystems",
    "drone": "Drone bay", "charge": "Charges and ammunition", "implant": "Implants", "cargo": "Cargo",
}


def layout(parsed: dict, types: dict) -> dict:
    """Group the items by slot using the type information: {'hull': {...}, 'slots': {slot: [rows]}, 'unknown': [names]}.
    types maps a lower-cased name to {'type_id', 'name', 'slot', 'volume'}. A row: type_id, name, quantity,
    charge (dict or None). Modules with the same type and charge are merged into one row with a count."""
    hull = types.get(parsed["hull"].lower())
    slots = {s: [] for s in SLOT_ORDER}
    unknown = []
    merged = OrderedDict()
    for it in parsed["items"]:
        t = types.get(it["name"].lower())
        if t is None:
            unknown.append(it["name"])
            continue
        charge = types.get(it["charge"].lower()) if it.get("charge") else None
        if it.get("charge") and charge is None:
            unknown.append(it["charge"])
        slot = t.get("slot") or "cargo"
        if slot in ("high", "mid", "low", "rig", "subsystem"):
            key = (slot, t["type_id"], charge["type_id"] if charge else None)
            row = merged.get(key)
            if row is None:
                row = {"type_id": t["type_id"], "name": t["name"], "quantity": 0, "charge": charge, "slot": slot}
                merged[key] = row
                slots[slot].append(row)
            row["quantity"] += it["quantity"]
        else:
            key = (slot, t["type_id"], None)
            row = merged.get(key)
            if row is None:
                row = {"type_id": t["type_id"], "name": t["name"], "quantity": 0, "charge": None, "slot": slot}
                merged[key] = row
                slots[slot].append(row)
            row["quantity"] += it["quantity"]
    return {"hull": hull, "slots": slots, "unknown": sorted(set(unknown))}


def cost(layout_data: dict, prices: dict) -> dict:
    """Jita cost of the fitting from {type_id: sell_min}: hull, fit (modules, rigs, subsystems), drones,
    charges and cargo, total, and the type ids without a price. Pure."""
    missing = []

    def price_of(type_id, quantity):
        p = prices.get(type_id)
        if p is None:
            missing.append(type_id)
            return 0.0
        return p * quantity

    hull = layout_data["hull"]
    hull_cost = price_of(hull["type_id"], 1) if hull else 0.0
    fit = sum(price_of(r["type_id"], r["quantity"]) for s in ("high", "mid", "low", "rig", "subsystem") for r in layout_data["slots"][s])
    fit += sum(price_of(r["charge"]["type_id"], r["quantity"]) for s in ("high", "mid", "low") for r in layout_data["slots"][s] if r.get("charge"))
    drones = sum(price_of(r["type_id"], r["quantity"]) for r in layout_data["slots"]["drone"])
    charges = sum(price_of(r["type_id"], r["quantity"]) for s in ("charge", "cargo", "implant") for r in layout_data["slots"][s])
    return {"hull": hull_cost, "fit": fit, "drones": drones, "cargo": charges, "total": hull_cost + fit + drones + charges, "missing": sorted(set(missing))}


def eft_text(parsed: dict) -> str:
    """The fitting back as EFT text, normalised (what the Copy button puts on the clipboard)."""
    out = [f"[{parsed['hull']}, {parsed['name']}]"]
    for it in parsed["items"]:
        line = it["name"]
        if it.get("charge"):
            line += f", {it['charge']}"
        if it["quantity"] != 1:
            line += f" x{it['quantity']}"
        out.append(line)
    return "\n".join(out)
