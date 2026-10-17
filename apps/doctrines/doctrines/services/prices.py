"""Prices for every type that appears in a fitting: Fuzzwork's station aggregates (Jita IV-4), lowest sell."""

import datetime as dt
import logging

from django.utils import timezone

from .. import app_settings
from ..models import DoctrineShip, TypePrice
from . import get_json, polite_pause

logger = logging.getLogger(__name__)

AGGREGATES_URL = "https://market.fuzzwork.co.uk/aggregates/"


def type_ids_in_use() -> set[int]:
    """Every type id in an active fitting: hull, modules, charges, drones, cargo."""
    ids = set()
    for ship in DoctrineShip.objects.filter(is_active=True):
        if ship.ship_type_id:
            ids.add(ship.ship_type_id)
        for slot_rows in (ship.fitting_json or {}).get("slots", {}).values():
            for row in slot_rows:
                ids.add(int(row["type_id"]))
                if row.get("charge"):
                    ids.add(int(row["charge"]["type_id"]))
    return ids


def _f(value):
    try:
        v = float(value)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def refresh(type_ids=None) -> dict:
    """Read the aggregates for the given (or all used) type ids and store sell_min and buy_max."""
    ids = sorted(type_ids if type_ids is not None else type_ids_in_use())
    station = int(app_settings.DOCTRINES_MARKET_STATION_ID)
    now = timezone.now()
    updated = 0
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        data = get_json(AGGREGATES_URL, params={"station": station, "types": ",".join(map(str, chunk))})
        for type_id in chunk:
            row = data.get(str(type_id)) or {}
            sell = _f((row.get("sell") or {}).get("min"))
            buy = _f((row.get("buy") or {}).get("max"))
            TypePrice.objects.update_or_create(type_id=type_id, defaults={"sell_min": sell, "buy_max": buy, "updated_at": now})
            updated += 1
        polite_pause()
    return {"updated": updated, "types": len(ids)}


def price_map(type_ids) -> dict:
    """{type_id: sell_min} for the given ids (None values left out)."""
    return {p.type_id: p.sell_min for p in TypePrice.objects.filter(type_id__in=list(type_ids)) if p.sell_min}


def freshness():
    """When the prices were last refreshed, or None."""
    p = TypePrice.objects.order_by("-updated_at").first()
    return p.updated_at if p else None


def is_stale() -> bool:
    at = freshness()
    return at is None or timezone.now() - at > dt.timedelta(hours=app_settings.DOCTRINES_PRICE_MAX_AGE_HOURS)
