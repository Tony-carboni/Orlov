"""Scrapmetal tab: meta modules worth buying at Jita to reprocess for their minerals.

Owner's story (2026-10-08): he buys these modules to reprocess them. Module reprocessing
is not affected by the structure, rigs or implants, only by the Scrapmetal Processing
skill, so he does it at 0 % tax in the Isikano Raitaru. The question is which modules
are favourable to buy, given the Jita sell value of what they give.

Yield = 50 % + 2 % per level of Scrapmetal Processing (55 % at V). The game rounds each
mineral down per unit reprocessed, as the owner's sheet does (ROUNDDOWN(0.55 × qty)).
Value per unit = Σ floor(quantity × yield) × Jita lowest sell, × (1 − tax).

Catalog: the owner's list of modules in constants.SCRAP_GROUPS (names → type ids through
ESI, materials through EVE Ref); managers can add more rows in the admin. Figures and
filters mirror the Reprocessing tab (services/reprocessing.py).
"""

import logging
import math
import re
from dataclasses import dataclass, field

from django.utils import timezone

from .. import app_settings, constants
from ..models import MaterialType, PriceSnapshot, ScrapItem
from . import everef
from .http import get_json, polite_pause, session

logger = logging.getLogger(__name__)

SKILL_SCRAPMETAL = constants.SKILL_SCRAPMETAL
VARIANT_WORDS = ["Compact", "Enduring", "Scoped", "Restrained", "Ample"]
VARIANT_ORDER = VARIANT_WORDS + ["other"]
ESI_IDS_URL = "https://esi.evetech.net/latest/universe/ids/"


# --- yield -------------------------------------------------------------------------

def yield_fraction(level: int) -> float:
    """50 % + 2 % per level of Scrapmetal Processing: 0.55 at V."""
    level = max(0, min(5, int(level or 0)))
    return 0.5 * (1.0 + 0.02 * level)


def skill_level(settings) -> int:
    """The member's Scrapmetal Processing level; the owner's default when no character is loaded."""
    if settings is not None and getattr(settings, "skills_character_id", None):
        return int(getattr(settings, "scrapmetal_processing", 0) or 0)
    return int(app_settings.SHIPYARD_SCRAP_SKILL_DEFAULT)


def setup_summary(settings=None) -> dict:
    level = skill_level(settings)
    return {
        "location": app_settings.SHIPYARD_SCRAP_LOCATION,
        "tax": float(app_settings.SHIPYARD_SCRAP_TAX),
        "level": level,
        "yield": yield_fraction(level),
        "price_points": list(app_settings.SHIPYARD_SCRAP_PRICE_POINTS),
        "from_character": bool(settings is not None and getattr(settings, "skills_character_id", None)),
    }


def unit_outputs(materials: dict, yield_fraction_: float) -> dict:
    """{type_id: units} one module gives, each mineral rounded down as the game does."""
    return {int(k): math.floor(float(q) * yield_fraction_) for k, q in materials.items()}


# --- catalog -----------------------------------------------------------------------------

def variant_of(name: str) -> str:
    for word in VARIANT_WORDS:
        if re.search(rf"\b{word}\b", name):
            return word
    return "other"


def group_of(name: str):
    """(group label, order) from the owner's list, or (None, None) for a name not in it."""
    for order, (label, names) in enumerate(constants.SCRAP_GROUPS):
        if name in names:
            return label, order
    return None, None


def resolve_type_ids(names: list) -> dict:
    """{name: type id} through ESI's name lookup (exact names, chunks of 100)."""
    out = {}
    names = [n for n in names if n]
    for i in range(0, len(names), 100):
        chunk = names[i:i + 100]
        r = session().post(ESI_IDS_URL, params={"datasource": "tranquility"}, json=chunk, timeout=30)
        r.raise_for_status()
        for row in r.json().get("inventory_types") or []:
            out[row["name"]] = int(row["id"])
        polite_pause()
    return out


def import_catalog() -> dict:
    """Make sure every module of the owner's list exists, then refresh materials for all rows."""
    wanted = [(label, order, name) for order, (label, names) in enumerate(constants.SCRAP_GROUPS) for name in names]
    missing = [name for _, _, name in wanted if not ScrapItem.objects.filter(name=name).exists()]
    ids = resolve_type_ids(missing) if missing else {}
    created, unresolved = 0, []
    for label, order, name in wanted:
        item = ScrapItem.objects.filter(name=name).first()
        if item is None:
            if name not in ids:
                unresolved.append(name)
                continue
            item = ScrapItem(type_id=ids[name], name=name)
            created += 1
        item.group = label
        item.group_order = order
        item.save()
    refreshed, errors = 0, []
    for item in ScrapItem.objects.filter(is_active=True):
        try:
            t = everef.get_type(item.type_id)
            item.name = everef.type_name(t) or item.name
            item.materials = {str(k): float(v["quantity"]) for k, v in (t.get("type_materials") or {}).items()}
            item.volume = float(t.get("packaged_volume") or t.get("volume") or 0)
            item.portion_size = int(t.get("portion_size") or 1)
            item.meta_level = int(t.get("meta_level") or 0)
            item.variant = variant_of(item.name)
            if not item.group:
                item.group, item.group_order = group_of(item.name)[0] or "Other", group_of(item.name)[1] or 999
            item.updated_at = timezone.now()
            item.save()
            refreshed += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{item.name}: {exc}")
            logger.warning("scrap item %s not read from EVE Ref: %s", item.name, exc)
        polite_pause()
    out_ids = output_type_ids()
    known = set(MaterialType.objects.filter(type_id__in=out_ids).values_list("type_id", flat=True))
    for tid in sorted(out_ids - known):
        try:
            t = everef.get_type(tid)
            MaterialType.objects.update_or_create(type_id=tid, defaults={"name": everef.type_name(t), "volume": float(t.get("volume") or 0)})
        except Exception as exc:  # noqa: BLE001
            logger.warning("material %s not read from EVE Ref: %s", tid, exc)
        polite_pause()
    return {"items": ScrapItem.objects.filter(is_active=True).count(), "created": created, "refreshed": refreshed,
            "unresolved": unresolved, "errors": errors}


def output_type_ids() -> set:
    ids = set()
    for mats in ScrapItem.objects.filter(is_active=True).values_list("materials", flat=True):
        ids.update(int(k) for k in mats)
    return ids


def type_ids() -> set:
    return set(ScrapItem.objects.filter(is_active=True).values_list("type_id", flat=True))


# --- dashboard rows ---------------------------------------------------------------------

@dataclass
class Output:
    type_id: int
    name: str
    quantity: int
    unit_price: float | None
    value: float | None
    share: float | None = None  # of the module's gross value; None while the mineral has no price


@dataclass
class ScrapRow:
    item: ScrapItem
    yield_fraction: float
    outputs: list = field(default_factory=list)
    gross_value: float = 0.0
    net_value: float = 0.0
    sell_price: float | None = None
    buy_price: float | None = None
    missing: int = 0
    sell_volume: float = 0.0

    @property
    def complete(self):
        return self.missing == 0 and self.net_value > 0

    @property
    def sell_ratio(self):
        return self.sell_price / self.net_value if self.sell_price and self.net_value else None

    @property
    def buy_ratio(self):
        return self.buy_price / self.net_value if self.buy_price and self.net_value else None

    @property
    def price_points(self):
        return [(p, self.net_value * p / 100.0) for p in app_settings.SHIPYARD_SCRAP_PRICE_POINTS]

    @property
    def market_depth_days(self):
        return self.sell_volume / self.item.avg_daily_volume if self.item.avg_daily_volume else None

    @property
    def margin_per_unit(self):
        return (self.net_value - self.sell_price) if self.sell_price is not None else None


def dashboard_rows(market, settings=None) -> list[ScrapRow]:
    level = skill_level(settings)
    y = yield_fraction(level)
    tax = float(app_settings.SHIPYARD_SCRAP_TAX)
    items = list(ScrapItem.objects.filter(is_active=True).order_by("group_order", "group", "name"))
    mat_ids = {int(k) for i in items for k in i.materials}
    prices = {}
    if market is not None:
        prices = {p.type_id: p for p in PriceSnapshot.objects.filter(location=market, type_id__in=mat_ids | {i.type_id for i in items})}
    names = {m.type_id: m.name for m in MaterialType.objects.filter(type_id__in=mat_ids)}
    rows = []
    for item in items:
        outputs, gross, missing = [], 0.0, 0
        for tid, qty in unit_outputs(item.materials, y).items():
            if qty <= 0:
                continue
            p = prices.get(tid)
            unit_price = p.sell_min if p else None
            value = qty * unit_price if unit_price is not None else None
            if value is None:
                missing += 1
            else:
                gross += value
            outputs.append(Output(type_id=tid, name=names.get(tid, f"Type {tid}"), quantity=qty, unit_price=unit_price, value=value))
        outputs.sort(key=lambda o: -(o.value or 0))
        for o in outputs:
            o.share = (o.value / gross) if (gross and o.value is not None) else None
        p = prices.get(item.type_id)
        rows.append(ScrapRow(
            item=item, yield_fraction=y, outputs=outputs, gross_value=gross, net_value=gross * (1.0 - tax),
            sell_price=p.sell_min if p else None, buy_price=p.buy_max if p else None, missing=missing,
            sell_volume=p.sell_volume if p else 0.0,
        ))
    rows.sort(key=lambda r: (r.sell_ratio is None, r.sell_ratio or 0))  # modules are bought from sell orders
    return rows


def groups_present(items=None) -> list[str]:
    items = items if items is not None else ScrapItem.objects.filter(is_active=True)
    return [g for _, g in sorted({(i.group_order, i.group) for i in items})]


def variants_present(items=None) -> list[str]:
    items = items if items is not None else ScrapItem.objects.filter(is_active=True)
    present = {i.variant for i in items}
    return [v for v in VARIANT_ORDER if v in present]
