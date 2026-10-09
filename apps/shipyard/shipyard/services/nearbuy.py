"""Buy orders that reach the market station from nearby systems (owner, 2026-10-09).

Fuzzwork's station aggregates only see orders placed at Jita 4-4. A buy order placed in
Perimeter with a range of one jump (or more, or the region) also buys from a seller standing
in Jita, so for the owner's buy-order story those count too. ESI's regional order list carries
each order's location and range, so per type we take every buy order that reaches the station.
"""

import logging

from django.utils import timezone

from .. import app_settings
from ..models import PriceSnapshot
from . import esi
from .http import polite_pause

logger = logging.getLogger(__name__)


def reaches(order: dict, station_id: int, near_systems: dict) -> bool:
    """Does this buy order accept a sale made at `station_id`?"""
    rng = str(order.get("range") or "")
    if int(order.get("location_id") or 0) == int(station_id):
        return True
    if rng == "region":
        return True
    jumps = near_systems.get(int(order.get("system_id") or 0))
    if jumps is None:
        return False
    if jumps == 0:
        return rng != "station"
    if rng == "solarsystem" or rng == "station":
        return False
    try:
        return int(rng) >= jumps
    except ValueError:
        return False


def effective_buy_max(orders, station_id: int, near_systems: dict) -> float | None:
    """Highest price among the buy orders that reach the station, None without any."""
    prices = [float(o["price"]) for o in orders if reaches(o, station_id, near_systems) and float(o.get("volume_remain") or 0) > 0]
    return max(prices) if prices else None


def refresh(location, type_ids) -> tuple[int, list]:
    """Fill PriceSnapshot.buy_max_near for these types at this market location."""
    near = {int(k): int(v) for k, v in app_settings.SHIPYARD_NEAR_BUY_SYSTEMS.items()}
    n, errors = 0, []
    for tid in sorted(int(t) for t in type_ids):
        try:
            orders = esi.buy_orders(location.region_id, tid)
            PriceSnapshot.objects.update_or_create(
                type_id=tid, location=location,
                defaults={"buy_max_near": effective_buy_max(orders, location.station_id, near), "fetched_at": timezone.now()},
            )
            n += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{tid}: {exc}")
            logger.warning("near buy orders failed for %s: %s", tid, exc)
        polite_pause()
    return n, errors
