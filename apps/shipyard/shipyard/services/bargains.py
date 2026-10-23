"""Bargains: every type traded in The Forge against its own year (owner, 2026-10-23: "pull in all the
items in Jita and flag those on 52-week lows or at exceptionally good prices").

Good citizenship first. The year of history does not come from ESI (that would be one call per type,
some 10,000 a night): it comes from EVE Ref's daily market-history archives (data.everef.net, one
bzip2 CSV a day for every region, about 600 KB, built from ESI by EVE Ref, full downloads allowed),
one small download a day. The Forge rows of each day are kept compressed in the database
(MarketHistoryDay) so the year can be recomputed at any time; a day whose record count in EVE Ref's
totals.json changed is fetched again (archives are completed in place). Names come from ESI's public
names route (1,000 ids a call, only for types without a name yet); the market-group path from EVE
Ref's reference-data archive (market_groups.json, cached a week). Jita 4-4 prices come from Fuzzwork's
station aggregates (100 types a call) for the types that traded in the last 30 days, every two hours.

Flags: "52-week low" when Jita's lowest sell is within SHIPYARD_BARGAIN_LOW_PCT (5 %) of the lowest
daily low of the last 365 days; "under its 90-day average" when it is SHIPYARD_BARGAIN_DIP_PCT (20 %)
or more below the volume-weighted 90-day average. Thin markets hide behind the ISK-per-day filter.
"""

import bz2
import datetime as dt
import io
import json
import logging
import tarfile
import tempfile
import time
import zlib
from collections import defaultdict

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .. import app_settings, constants
from ..models import MarketHistoryDay, MarketTypeStat
from . import fuzzwork
from .http import get_json, session

logger = logging.getLogger(__name__)

HISTORY_URL = "https://data.everef.net/market-history/{year}/market-history-{day}.csv.bz2"
TOTALS_URL = "https://data.everef.net/market-history/totals.json"
REFDATA_URL = "https://data.everef.net/reference-data/reference-data-latest.tar.xz"
NAMES_URL = "https://esi.evetech.net/latest/universe/names/"
REGION = constants.THE_FORGE_REGION_ID
STATION = constants.JITA_44_STATION_ID
YEAR = 365
GROUPS_CACHE_KEY = "shipyard:bargains:groups"
GROUPS_CACHE_SECONDS = 8 * 86400
PAUSE = 0.3  # between archive downloads


# --- history archive ------------------------------------------------------------------------------

def _forge_rows(csv_text: str) -> list[str]:
    """Compact lines 'type_id,average,lowest,highest,volume,order_count' of The Forge out of a day's CSV."""
    out = []
    lines = csv_text.splitlines()
    if not lines:
        return out
    header = lines[0].split(",")
    try:
        ix = {k: header.index(k) for k in ("average", "highest", "lowest", "order_count", "volume", "region_id", "type_id")}
    except ValueError as exc:
        raise ValueError(f"unexpected archive columns: {header}") from exc
    want = str(REGION)
    for line in lines[1:]:
        f = line.split(",")
        if len(f) <= ix["type_id"] or f[ix["region_id"]] != want:
            continue
        out.append(",".join((f[ix["type_id"]], f[ix["average"]], f[ix["lowest"]], f[ix["highest"]], f[ix["volume"]], f[ix["order_count"]])))
    return out


def pack(rows: list[str]) -> bytes:
    return zlib.compress("\n".join(rows).encode("utf-8"), 6)


def unpack(blob: bytes):
    """Yields (type_id, average, lowest, highest, volume, order_count)."""
    text = zlib.decompress(bytes(blob)).decode("utf-8")
    for line in text.splitlines():
        f = line.split(",")
        if len(f) < 6:
            continue
        yield int(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[4]), int(float(f[5]))


def fetch_day(day: dt.date) -> list[str]:
    r = session().get(HISTORY_URL.format(year=day.year, day=day.isoformat()), timeout=120)
    r.raise_for_status()
    return _forge_rows(bz2.decompress(r.content).decode("utf-8"))


def sync_history(days: int | None = None, max_downloads: int | None = None, today: dt.date | None = None) -> dict:
    """Fetch the day archives that are new or were completed since (totals.json), keep the last `days`."""
    days = days or app_settings.SHIPYARD_BARGAIN_DAYS
    today = today or timezone.now().date()
    totals = get_json(TOTALS_URL)
    have = {d.day: d.total for d in MarketHistoryDay.objects.only("day", "total")}
    oldest = today - dt.timedelta(days=days)
    downloaded, skipped, missing = 0, 0, 0
    for back in range(1, days + 1):
        day = today - dt.timedelta(days=back)
        expected = totals.get(day.isoformat())
        if expected is None:
            missing += 1
            continue
        if have.get(day) == int(expected):
            skipped += 1
            continue
        if max_downloads is not None and downloaded >= max_downloads:
            break
        try:
            rows = fetch_day(day)
        except Exception as exc:  # noqa: BLE001
            logger.warning("bargains: archive %s failed: %s", day, exc)
            missing += 1
            continue
        MarketHistoryDay.objects.update_or_create(day=day, defaults={"total": int(expected), "rows": len(rows), "data": pack(rows), "fetched_at": timezone.now()})
        downloaded += 1
        time.sleep(PAUSE)
    dropped = MarketHistoryDay.objects.filter(day__lt=oldest).delete()[0]
    return {"downloaded": downloaded, "skipped": skipped, "missing": missing, "dropped": dropped, "days": MarketHistoryDay.objects.count()}


# --- the year per type ----------------------------------------------------------------------------

def _wavg(pv: float, v: float, p_sum: float, n: int):
    """Volume-weighted average price; the plain mean when no volume was recorded; None without rows."""
    if v > 0:
        return pv / v
    return (p_sum / n) if n else None


def compute_stats() -> int:
    """Rebuild every type's year from the stored days: 52-week low and high (with dates), volume-weighted
    30, 90 and 365-day averages, days traded, units and ISK a day over 30 days, the last day's figures."""
    newest = MarketHistoryDay.objects.order_by("-day").values_list("day", flat=True).first()
    if newest is None:
        return 0
    start = newest - dt.timedelta(days=YEAR - 1)
    d90 = newest - dt.timedelta(days=89)
    d30 = newest - dt.timedelta(days=29)
    acc = {}
    for rec in MarketHistoryDay.objects.filter(day__gte=start).order_by("day").iterator(chunk_size=20):
        day = rec.day
        in90, in30 = day >= d90, day >= d30
        for tid, avg, low, high, vol, orders in unpack(rec.data):
            a = acc.get(tid)
            if a is None:
                a = acc[tid] = {"low": low, "low_d": day, "high": high, "high_d": day, "pv365": 0.0, "v365": 0.0, "p365": 0.0, "n365": 0,
                                "pv90": 0.0, "v90": 0.0, "p90": 0.0, "n90": 0, "pv30": 0.0, "v30": 0.0, "p30": 0.0, "n30": 0,
                                "last_d": day, "last_avg": avg, "last_low": low}
            if low < a["low"]:
                a["low"], a["low_d"] = low, day
            if high > a["high"]:
                a["high"], a["high_d"] = high, day
            a["pv365"] += avg * vol
            a["v365"] += vol
            a["p365"] += avg
            a["n365"] += 1
            if in90:
                a["pv90"] += avg * vol
                a["v90"] += vol
                a["p90"] += avg
                a["n90"] += 1
            if in30:
                a["pv30"] += avg * vol
                a["v30"] += vol
                a["p30"] += avg
                a["n30"] += 1
            if day >= a["last_d"]:
                a["last_d"], a["last_avg"], a["last_low"] = day, avg, low
    existing = {s.type_id: s for s in MarketTypeStat.objects.all()}
    create, update = [], []
    fields = ["as_of", "last_date", "last_avg", "last_low", "low52", "low52_date", "high52", "high52_date", "avg30", "avg90", "avg365",
              "days365", "vol30", "isk30", "updated_at"]
    now = timezone.now()
    for tid, a in acc.items():
        values = {"as_of": newest, "last_date": a["last_d"], "last_avg": a["last_avg"], "last_low": a["last_low"],
                  "low52": a["low"], "low52_date": a["low_d"], "high52": a["high"], "high52_date": a["high_d"],
                  "avg30": _wavg(a["pv30"], a["v30"], a["p30"], a["n30"]), "avg90": _wavg(a["pv90"], a["v90"], a["p90"], a["n90"]),
                  "avg365": _wavg(a["pv365"], a["v365"], a["p365"], a["n365"]), "days365": a["n365"],
                  "vol30": a["v30"] / 30.0, "isk30": a["pv30"] / 30.0, "updated_at": now}
        s = existing.get(tid)
        if s is None:
            create.append(MarketTypeStat(type_id=tid, **values))
        else:
            for k, v in values.items():
                setattr(s, k, v)
            update.append(s)
    with transaction.atomic():
        MarketTypeStat.objects.bulk_create(create, batch_size=1000)
        MarketTypeStat.objects.bulk_update(update, fields, batch_size=1000)
        # a type that stopped trading a year ago drops out
        MarketTypeStat.objects.exclude(type_id__in=list(acc)).delete()
    apply_flags()
    return len(acc)


# --- names and groups -----------------------------------------------------------------------------

def _names(ids: list[int]) -> dict[int, str]:
    """ESI's public names route; a batch with an invalid id answers 404, so split until it works."""
    if not ids:
        return {}
    r = session().post(NAMES_URL, params={"datasource": "tranquility"}, json=[int(i) for i in ids], timeout=60)
    if r.status_code == 404 and len(ids) > 1:
        half = len(ids) // 2
        return {**_names(ids[:half]), **_names(ids[half:])}
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    return {int(x["id"]): str(x.get("name") or "") for x in r.json() or []}


def fill_names() -> int:
    ids = list(MarketTypeStat.objects.filter(name="").values_list("type_id", flat=True))
    n = 0
    for i in range(0, len(ids), 1000):
        found = _names(ids[i:i + 1000])
        for tid, name in found.items():
            if name:
                MarketTypeStat.objects.filter(type_id=tid).update(name=name[:100])
                n += 1
        time.sleep(0.2)
    return n


def _group_paths(groups: dict) -> dict[int, tuple[int, str, str]]:
    """{type_id: (market_group_id, 'Top › ... › Leaf', 'Top')} out of EVE Ref's market_groups.json."""
    def name(g):
        n = g.get("name")
        return (n.get("en") if isinstance(n, dict) else str(n or "")) or "?"

    def chain(gid):
        out, seen = [], set()
        while gid is not None and str(gid) in groups and gid not in seen:
            seen.add(gid)
            g = groups[str(gid)]
            out.append(name(g))
            gid = g.get("parent_group_id")
        return list(reversed(out))

    out = {}
    for gid, g in groups.items():
        tids = g.get("type_ids") or []
        if not tids:
            continue
        names = chain(int(gid))
        path = " › ".join(names)[:300]
        top = names[0][:100] if names else ""
        for tid in tids:
            out[int(tid)] = (int(gid), path, top)
    return out


def groups_map(force: bool = False) -> dict:
    """The type → market-group map, from the cache or a fresh reference-data archive (54 MB, weekly)."""
    if not force:
        cached = cache.get(GROUPS_CACHE_KEY)
        if cached:
            return cached
    with tempfile.TemporaryFile() as tmp:
        with session().get(REFDATA_URL, stream=True, timeout=600) as r:
            r.raise_for_status()
            for chunk in r.iter_content(1 << 20):
                tmp.write(chunk)
        tmp.seek(0)
        groups = None
        with tarfile.open(fileobj=tmp, mode="r:xz") as tar:
            for m in tar:
                if m.name.endswith("market_groups.json"):
                    groups = json.load(io.TextIOWrapper(tar.extractfile(m), encoding="utf-8"))
                    break
    if groups is None:
        raise RuntimeError("market_groups.json not in the reference-data archive")
    out = _group_paths(groups)
    cache.set(GROUPS_CACHE_KEY, out, GROUPS_CACHE_SECONDS)
    return out


def fill_groups(force: bool = False) -> int:
    gm = groups_map(force=force)
    n = 0
    for s in MarketTypeStat.objects.all().only("type_id", "market_group_id", "group_path", "top_group"):
        g = gm.get(s.type_id)
        if g and (s.market_group_id, s.group_path, s.top_group) != g:
            s.market_group_id, s.group_path, s.top_group = g
            s.save(update_fields=["market_group_id", "group_path", "top_group"])
            n += 1
    return n


# --- prices and flags -----------------------------------------------------------------------------

def refresh_prices() -> dict:
    """Jita 4-4 lowest sell and highest buy for every type that traded in the last 30 days (Fuzzwork, 100 a call)."""
    ids = list(MarketTypeStat.objects.filter(isk30__gt=0).values_list("type_id", flat=True))
    agg = fuzzwork.station_aggregates(STATION, ids)
    now = timezone.now()
    n = 0
    for tid, a in agg.items():
        # no sell order at Jita 4-4 comes back as a price of 0: that is no price, not a bargain (0.29.2)
        sell = a["sell_min"] if (a["sell_min"] and a["sell_orders"]) else None
        buy = a["buy_max"] if a["buy_max"] else None
        n += MarketTypeStat.objects.filter(type_id=tid).update(sell_min=sell, buy_max=buy, sell_volume=a["sell_volume"],
                                                               sell_orders=a["sell_orders"], prices_at=now)
    apply_flags()
    return {"types": n, "asked": len(ids)}


def apply_flags() -> int:
    low_pct = app_settings.SHIPYARD_BARGAIN_LOW_PCT
    dip_pct = app_settings.SHIPYARD_BARGAIN_DIP_PCT
    rows = list(MarketTypeStat.objects.exclude(sell_min=None).exclude(low52=None))
    for s in rows:
        sell = s.sell_min
        span = (s.high52 or 0) - (s.low52 or 0)
        s.pos52 = ((sell - s.low52) / span) if span > 0 else 0.0
        s.vs90 = (sell / s.avg90 - 1) if s.avg90 else None
        s.vs365 = (sell / s.avg365 - 1) if s.avg365 else None
        s.flag_low = bool(s.low52 and sell <= s.low52 * (1 + low_pct))
        s.flag_dip = bool(s.vs90 is not None and s.vs90 <= -dip_pct + 1e-9)
    MarketTypeStat.objects.bulk_update(rows, ["pos52", "vs90", "vs365", "flag_low", "flag_dip"], batch_size=1000)
    return len(rows)


# --- the page -------------------------------------------------------------------------------------

def rows(min_isk: float = 0.0, top: str = "", flag: str = "any", q: str = "", limit: int = 600) -> list:
    qs = MarketTypeStat.objects.exclude(sell_min=None).exclude(low52=None).filter(isk30__gte=min_isk)
    if top:
        qs = qs.filter(top_group=top)
    if q:
        qs = qs.filter(name__icontains=q)
    if flag == "low":
        qs = qs.filter(flag_low=True)
    elif flag == "dip":
        qs = qs.filter(flag_dip=True)
    elif flag == "both":
        qs = qs.filter(flag_low=True, flag_dip=True)
    elif flag == "any":
        qs = qs.filter(models_q_any())
    return list(qs.order_by("vs90", "-isk30")[:limit])


def models_q_any():
    from django.db.models import Q
    return Q(flag_low=True) | Q(flag_dip=True)


def top_groups() -> list[tuple[str, int]]:
    from django.db.models import Count
    qs = MarketTypeStat.objects.exclude(top_group="").values("top_group").annotate(n=Count("type_id")).order_by("top_group")
    return [(r["top_group"], r["n"]) for r in qs]


def freshness() -> dict:
    newest = MarketHistoryDay.objects.order_by("-day").values_list("day", flat=True).first()
    return {"history_day": newest, "days": MarketHistoryDay.objects.count(), "types": MarketTypeStat.objects.count(),
            "priced": MarketTypeStat.objects.exclude(sell_min=None).count(),
            "prices_at": MarketTypeStat.objects.exclude(prices_at=None).order_by("-prices_at").values_list("prices_at", flat=True).first(),
            "flag_low": MarketTypeStat.objects.filter(flag_low=True).count(), "flag_dip": MarketTypeStat.objects.filter(flag_dip=True).count()}
