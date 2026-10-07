"""Fuzzwork market aggregates (per station)."""

import logging

from .http import get_json, polite_pause

logger = logging.getLogger(__name__)

AGGREGATES_URL = "https://market.fuzzwork.co.uk/aggregates/"
CHUNK = 100


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def station_aggregates(station_id: int, type_ids) -> dict[int, dict]:
    """Return {type_id: {sell_min, sell_percentile, sell_volume, sell_orders, buy_max}}."""
    out = {}
    ids = sorted({int(t) for t in type_ids})
    for i in range(0, len(ids), CHUNK):
        chunk = ids[i:i + CHUNK]
        data = get_json(AGGREGATES_URL, params={"station": int(station_id), "types": ",".join(map(str, chunk))})
        for tid, agg in data.items():
            sell = agg.get("sell") or {}
            buy = agg.get("buy") or {}
            out[int(tid)] = {
                "sell_min": _f(sell.get("min")),
                "sell_percentile": _f(sell.get("percentile")),
                "sell_volume": _f(sell.get("volume")) or 0.0,
                "sell_orders": int(_f(sell.get("orderCount")) or 0),
                "buy_max": _f(buy.get("max")),
            }
        polite_pause()
    return out
