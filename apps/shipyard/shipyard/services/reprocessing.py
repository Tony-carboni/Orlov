"""Reprocessing dashboard: what compressed ore and ice is worth buying to reprocess.

Catalog: every published "Compressed …" type in EVE's Asteroid category (EVE Ref
reference data: groups, types, type_materials, portion sizes). Yield: the Upwell
formula (EVE University, checked 2026-10-08):

    yield = (50 + rig) % × (1 + security) × (1 + structure)
            × (1 + 0.03 × Reprocessing) × (1 + 0.02 × Reprocessing Efficiency)
            × (1 + 0.02 × ore-specific skill) × (1 + implant)

Owner's setup (app_settings.SHIPYARD_REPRO_*): T2-rigged Tatara in Sobaseki (high-sec),
all skills V, RX-804 implant, 2 % service tax → 80.9 % on ore, ice and moon ore.

Figures per unit of compressed ore: the minerals it gives (per unit = per portion ÷
portion size × yield, no batch rounding), their Jita value, the net value after the
structure tax, and the price points the owner wants (90, 92, 95, 98, 100 % of the net
value): the most you can pay for the ore to keep that share of the output value.
"""

import logging
import re
from dataclasses import dataclass, field

from django.utils import timezone

from .. import app_settings
from ..models import MaterialType, Ore, PriceSnapshot
from . import everef

logger = logging.getLogger(__name__)

ASTEROID_CATEGORY_ID = 25
# Variant codes, in display order. Asteroid, abyssal and ice ores carry a grade in the name
# ("Gneiss II-Grade"), moon ores an adjective ("Brimful Zeolites" +15 %, "Glistening Zeolites" +100 %).
VARIANT_ORDER = ["base", "0", "II", "III", "IV", "X", "+15", "+100"]
VARIANT_LABELS = {"base": "base", "0": "0-Grade", "II": "II-Grade", "III": "III-Grade", "IV": "IV-Grade",
                  "X": "X-Grade", "+15": "+15 %", "+100": "+100 %"}
GRADE_RE = re.compile(r"^(?P<base>.+?) (?P<grade>0|II|III|IV|X)-Grade$")
MOON_PLUS_15 = {"Brimful", "Copious", "Bountiful", "Lavish", "Replete"}
MOON_PLUS_100 = {"Glistening", "Twinkling", "Shining", "Shimmering", "Glowing"}
KINDS = ["ore", "ice", "moon", "abyssal"]
KIND_LABELS = {"ore": "Asteroid ore", "ice": "Ice", "moon": "Moon ore", "abyssal": "Abyssal ore"}
STRUCTURE_BONUS = {"tatara": 0.055, "athanor": 0.02, "other": 0.0}


# --- yield ---------------------------------------------------------------------------

def yield_fraction(kind: str) -> float:
    """Reprocessing yield for this kind of ore under the configured setup (0.809 = 80.9 %)."""
    rig = float(app_settings.SHIPYARD_REPRO_RIG.get(kind, app_settings.SHIPYARD_REPRO_RIG.get("ore", 0)))
    structure = STRUCTURE_BONUS.get(str(app_settings.SHIPYARD_REPRO_STRUCTURE).lower(), 0.0)
    skills = app_settings.SHIPYARD_REPRO_SKILLS
    y = (50.0 + rig) / 100.0
    y *= 1.0 + float(app_settings.SHIPYARD_REPRO_SECURITY) if rig else 1.0
    y *= 1.0 + structure
    y *= 1.0 + 0.03 * int(skills.get("reprocessing", 5))
    y *= 1.0 + 0.02 * int(skills.get("efficiency", 5))
    y *= 1.0 + 0.02 * int(skills.get("ore", 5))
    y *= 1.0 + float(app_settings.SHIPYARD_REPRO_IMPLANT)
    return y


def setup_summary() -> dict:
    return {
        "location": app_settings.SHIPYARD_REPRO_LOCATION,
        "structure": app_settings.SHIPYARD_REPRO_STRUCTURE,
        "tax": float(app_settings.SHIPYARD_REPRO_TAX),
        "implant": float(app_settings.SHIPYARD_REPRO_IMPLANT),
        "yields": {k: yield_fraction(k) for k in KINDS},
        "price_points": list(app_settings.SHIPYARD_REPRO_PRICE_POINTS),
    }


# --- catalog import (EVE Ref) ----------------------------------------------------------

def _kind_for(group_name: str, type_name: str) -> str:
    g = group_name.lower()
    if g == "ice":
        return "ice"
    if "moon" in g:
        return "moon"
    if g in ("bezdnacine", "rakovene", "talassonite") or "abyssal" in g:
        return "abyssal"
    return "ore"


def family_and_variant(name: str) -> tuple[str, str]:
    """("Gneiss", "II") for "Compressed Gneiss II-Grade"; ("Zeolites", "+15") for "Compressed Brimful Zeolites"."""
    n = name.replace("Compressed ", "", 1).strip()
    m = GRADE_RE.match(n)
    if m:
        return m.group("base"), m.group("grade")
    first, _, rest = n.partition(" ")
    if rest and first in MOON_PLUS_15:
        return rest, "+15"
    if rest and first in MOON_PLUS_100:
        return rest, "+100"
    return n, "base"


def _families(entries: list[dict]) -> None:
    """Fill `family` and `variant` in place from the names."""
    for e in entries:
        e["family"], e["variant"] = family_and_variant(e["name"])


def import_catalog() -> dict:
    """Read every published compressed ore type from EVE Ref into Ore; returns counts."""
    category = everef.get_category(ASTEROID_CATEGORY_ID)
    entries = []
    for gid in category.get("group_ids", []):
        group = everef.get_group(gid)
        gname = everef.type_name(group)
        for tid in group.get("type_ids", []):
            t = everef.get_type(tid)
            name = everef.type_name(t)
            if not t.get("published") or not name.startswith("Compressed "):
                continue
            materials = {int(k): float(v["quantity"]) for k, v in (t.get("type_materials") or {}).items()}
            if not materials:
                continue
            skills = t.get("required_skills") or {}
            entries.append({
                "type_id": int(tid), "name": name, "group_id": int(gid), "group_name": gname,
                "kind": _kind_for(gname, name), "portion_size": int(t.get("portion_size") or 1),
                "volume": float(t.get("volume") or 0), "materials": materials,
                "skill_id": int(next(iter(skills), 0)) if skills else None,
            })
    _families(entries)
    seen = set()
    for e in entries:
        Ore.objects.update_or_create(type_id=e["type_id"], defaults={
            "name": e["name"], "group_id": e["group_id"], "group_name": e["group_name"], "kind": e["kind"],
            "family": e["family"], "variant": e["variant"], "portion_size": e["portion_size"],
            "volume": e["volume"], "materials": {str(k): v for k, v in e["materials"].items()},
            "skill_id": e["skill_id"], "updated_at": timezone.now(),
        })
        seen.add(e["type_id"])
    gone = Ore.objects.exclude(type_id__in=seen).update(is_active=False)
    # names and volumes of the output materials
    out_ids = {int(k) for e in entries for k in e["materials"]}
    known = set(MaterialType.objects.filter(type_id__in=out_ids).values_list("type_id", flat=True))
    for tid in sorted(out_ids - known):
        try:
            t = everef.get_type(tid)
            MaterialType.objects.update_or_create(type_id=tid, defaults={"name": everef.type_name(t), "volume": float(t.get("volume") or 0)})
        except Exception as exc:  # noqa: BLE001
            logger.warning("material %s not read from EVE Ref: %s", tid, exc)
    return {"ores": len(entries), "families": len({e["family"] for e in entries}), "retired": gone, "materials": len(out_ids)}


def output_type_ids() -> set:
    ids = set()
    for mats in Ore.objects.filter(is_active=True).values_list("materials", flat=True):
        ids.update(int(k) for k in mats)
    return ids


# --- dashboard rows --------------------------------------------------------------------

@dataclass
class Output:
    type_id: int
    name: str
    quantity: float          # per unit of compressed ore, after yield
    unit_price: float | None
    value: float | None


@dataclass
class OreRow:
    ore: Ore
    yield_fraction: float
    outputs: list = field(default_factory=list)
    gross_value: float = 0.0        # per unit, before tax
    net_value: float = 0.0          # per unit, after the structure tax
    sell_price: float | None = None  # Jita lowest sell of the compressed ore
    buy_price: float | None = None   # Jita highest buy
    missing: int = 0                 # outputs without a price

    @property
    def complete(self):
        return self.missing == 0 and self.net_value > 0

    @property
    def sell_ratio(self):
        """Jita sell price as a share of the net output value (0.87 = 87 %)."""
        return self.sell_price / self.net_value if self.sell_price and self.net_value else None

    @property
    def buy_ratio(self):
        return self.buy_price / self.net_value if self.buy_price and self.net_value else None

    @property
    def price_points(self):
        return [(p, self.net_value * p / 100.0) for p in app_settings.SHIPYARD_REPRO_PRICE_POINTS]

    @property
    def margin_per_m3(self):
        """Net value minus sell price per m³ of compressed ore, for the hauler."""
        if self.sell_price is None or not self.ore.volume:
            return None
        return (self.net_value - self.sell_price) / self.ore.volume


def dashboard_rows(market) -> list[OreRow]:
    ores = sorted(Ore.objects.filter(is_active=True),
                  key=lambda o: (o.kind, o.family, VARIANT_ORDER.index(o.variant) if o.variant in VARIANT_ORDER else 99))
    mat_ids = {int(k) for o in ores for k in o.materials}
    type_ids = mat_ids | {o.type_id for o in ores}
    prices = {}
    if market is not None:
        prices = {p.type_id: p for p in PriceSnapshot.objects.filter(location=market, type_id__in=type_ids)}
    names = {m.type_id: m.name for m in MaterialType.objects.filter(type_id__in=mat_ids)}
    tax = float(app_settings.SHIPYARD_REPRO_TAX)
    rows = []
    for ore in ores:
        y = yield_fraction(ore.kind)
        outputs, gross, missing = [], 0.0, 0
        for k, qty in ore.materials.items():
            tid = int(k)
            per_unit = float(qty) / max(1, ore.portion_size) * y
            p = prices.get(tid)
            unit_price = p.sell_min if p else None
            value = per_unit * unit_price if unit_price is not None else None
            if value is None:
                missing += 1
            else:
                gross += value
            outputs.append(Output(type_id=tid, name=names.get(tid, f"Type {tid}"), quantity=per_unit, unit_price=unit_price, value=value))
        outputs.sort(key=lambda o: -(o.value or 0))
        p = prices.get(ore.type_id)
        rows.append(OreRow(
            ore=ore, yield_fraction=y, outputs=outputs, gross_value=gross, net_value=gross * (1.0 - tax),
            sell_price=p.sell_min if p else None, buy_price=p.buy_max if p else None, missing=missing,
        ))
    rows.sort(key=lambda r: (r.buy_ratio is None, r.buy_ratio or 0))  # the owner buys: buy-order share first
    return rows


def families_by_kind(ores=None) -> dict[str, list[str]]:
    ores = ores if ores is not None else Ore.objects.filter(is_active=True)
    out = {k: [] for k in KINDS}
    for kind, family in sorted(set(ores.values_list("kind", "family"))):
        out.setdefault(kind, []).append(family)
    return out


def variant_label(variant: str) -> str:
    return VARIANT_LABELS.get(variant, variant)


def variants_present(ores=None) -> list[tuple[str, str]]:
    """[(code, label)] of the variants in the catalog, in display order."""
    ores = ores if ores is not None else Ore.objects.filter(is_active=True)
    present = set(ores.values_list("variant", flat=True))
    return [(v, VARIANT_LABELS[v]) for v in VARIANT_ORDER if v in present] + sorted((v, v) for v in present if v not in VARIANT_ORDER)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
