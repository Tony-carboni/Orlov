"""Blueprint copy prices from public contracts, read from EVE Ref's half-hourly snapshot.

EVE Ref scrapes every public contract in the game (ESI, no token needed) twice an hour
and publishes one archive with two CSV files we use: `contracts.csv` and
`contract_items.csv` (docs/research/06-public-contract-blueprint-prices.md). One
download per refresh, no ESI calls.

The figure per ship is the owner's rule (2026-10-08): the average per-run price of the
cheapest N runs on offer, cheapest contracts first (N = SHIPYARD_CONTRACT_RUNS, 5).
Example: copies at 1, 2, 3, 3, 3 M each with one run → (1+2+3+3+3)/5 = 2.4 M per run.
"""

import csv
import io
import json
import logging
import tarfile
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.utils import timezone

from .. import app_settings
from ..models import ContractPrice, Ship
from .http import session

logger = logging.getLogger(__name__)


@dataclass
class Offer:
    """One public contract that sells only copies of one blueprint."""

    contract_id: int
    price: float          # ISK for the whole contract
    runs: int             # runs in the contract (runs × quantity, all copies together)
    me: int = 0
    te: int = 0
    station_id: int = 0
    region_id: int = 0
    date_expired: str = ""

    @property
    def per_run(self) -> float:
        return self.price / self.runs if self.runs else 0.0

    def as_dict(self) -> dict:
        return {"contract_id": self.contract_id, "price": self.price, "runs": self.runs, "per_run": round(self.per_run, 2),
                "me": self.me, "te": self.te, "station_id": self.station_id, "region_id": self.region_id,
                "date_expired": self.date_expired}


@dataclass
class ShipQuote:
    blueprint_type_id: int
    offers: list = field(default_factory=list)   # every matching offer, any order

    def sorted(self):
        return sorted(self.offers, key=lambda o: o.per_run)


def cheapest_runs_average(offers, want: int, outlier_factor: float | None = None) -> tuple[float | None, int, int]:
    """Average per-run price of the cheapest `want` runs, cheapest offers first.

    Returns (average, runs used, offers used). Fewer than `want` runs on offer → the
    average of what there is. Offers dearer than `outlier_factor` × the cheapest one are
    ignored (a 9 B listing next to three at 35 M is a mistake or a scam, not a price).
    """
    offers = sorted((o for o in offers if o.runs > 0 and o.price > 0), key=lambda o: o.per_run)
    if not offers:
        return None, 0, 0
    if outlier_factor:
        floor = offers[0].per_run
        offers = [o for o in offers if o.per_run <= floor * outlier_factor]
    got, total, used = 0, 0.0, 0
    for o in offers:
        take = min(o.runs, want - got)
        total += o.per_run * take
        got += take
        used += 1
        if got >= want:
            break
    return total / got, got, used


# --- snapshot download and parsing -----------------------------------------------------

def download(url: str | None = None) -> str:
    """Fetch the snapshot archive to a temporary file; returns its path."""
    url = url or app_settings.SHIPYARD_CONTRACTS_URL
    tmp = tempfile.NamedTemporaryFile(prefix="shipyard-contracts-", suffix=".tar.bz2", delete=False)
    with session().get(url, stream=True, timeout=app_settings.SHIPYARD_HTTP_TIMEOUT * 4,
                       headers={"Accept": "*/*"}) as r:
        r.raise_for_status()
        for chunk in r.iter_content(1 << 16):
            tmp.write(chunk)
    tmp.close()
    return tmp.name


def _member(tar: tarfile.TarFile, basename: str):
    for m in tar.getmembers():
        if m.name.split("/")[-1] == basename:
            return tar.extractfile(m)
    raise FileNotFoundError(f"{basename} not in the snapshot")


def _rows(tar: tarfile.TarFile, basename: str):
    return csv.DictReader(io.TextIOWrapper(_member(tar, basename), encoding="utf-8", newline=""))


def _true(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "t", "yes")


def parse_snapshot(path: str, blueprint_type_ids, regions=None, stations=None) -> tuple[dict[int, ShipQuote], datetime | None]:
    """Read one archive; returns ({blueprint_type_id: ShipQuote}, snapshot time).

    Only item-exchange contracts with a price, in the wanted regions and stations, whose included
    items are all copies of the same wanted blueprint, count. Bundles with anything
    else in them are skipped: their price says nothing about the blueprint alone.
    """
    wanted = {int(t) for t in blueprint_type_ids}
    regions = {int(r) for r in (regions if regions is not None else app_settings.SHIPYARD_CONTRACT_REGIONS)}
    stations = {int(s) for s in (stations if stations is not None else app_settings.SHIPYARD_CONTRACT_STATIONS)}
    quotes = {t: ShipQuote(blueprint_type_id=t) for t in wanted}
    with tarfile.open(path, mode="r:bz2") as tar:
        snapshot_at = None
        try:
            meta = json.loads(_member(tar, "meta.json").read().decode("utf-8"))
            snapshot_at = datetime.fromisoformat(meta["scrape_end"].replace("Z", "+00:00"))
        except Exception as exc:  # noqa: BLE001
            logger.info("snapshot meta not read: %s", exc)
        contracts = {}
        for row in _rows(tar, "contracts.csv"):
            if row.get("type") != "item_exchange":
                continue
            try:
                price = float(row.get("price") or 0)
                region = int(row.get("region_id") or 0)
                station = int(row.get("station_id") or row.get("start_location_id") or 0)
            except ValueError:
                continue
            if price <= 0 or (regions and region not in regions) or (stations and station not in stations):
                continue
            contracts[row["contract_id"]] = (price, region, station, row.get("date_expired") or "")
        items = defaultdict(list)
        for row in _rows(tar, "contract_items.csv"):
            cid = row.get("contract_id")
            if cid in contracts and _true(row.get("is_included")):
                items[cid].append(row)
    for cid, rows in items.items():
        try:
            type_ids = {int(r["type_id"]) for r in rows}
        except (TypeError, ValueError):
            continue
        if len(type_ids) != 1:
            continue
        tid = type_ids.pop()
        if tid not in wanted or not all(_true(r.get("is_blueprint_copy")) for r in rows):
            continue
        try:
            runs = sum(int(r.get("runs") or 0) * max(1, int(r.get("quantity") or 1)) for r in rows)
            me = int(rows[0].get("material_efficiency") or 0)
            te = int(rows[0].get("time_efficiency") or 0)
        except (TypeError, ValueError):
            continue
        if runs <= 0:
            continue
        price, region, station, expires = contracts[cid]
        quotes[tid].offers.append(Offer(contract_id=int(cid), price=price, runs=runs, me=me, te=te,
                                        station_id=int(station or 0), region_id=region, date_expired=expires))
    return quotes, snapshot_at


# --- refresh ---------------------------------------------------------------------------

def priced_ships():
    """Ships whose blueprint price comes from public contracts (owner's categories)."""
    return Ship.objects.filter(is_active=True, category__in=app_settings.SHIPYARD_CONTRACT_CATEGORIES)


def refresh(path: str | None = None) -> dict:
    """Download (unless a path is given), parse, store one ContractPrice row per ship.

    Ships without a single matching contract keep no row (the dashboard then says
    "Price not known"). Returns counts for the refresh log.
    """
    ships = {s.blueprint_type_id: s for s in priced_ships()}
    if not ships:
        return {"ships": 0, "priced": 0, "offers": 0}
    own_file = path is None
    path = path or download()
    try:
        quotes, snapshot_at = parse_snapshot(path, ships.keys())
    finally:
        if own_file:
            try:
                import os
                os.unlink(path)
            except OSError:
                pass
    snapshot_at = snapshot_at or timezone.now()
    want = app_settings.SHIPYARD_CONTRACT_RUNS
    factor = app_settings.SHIPYARD_CONTRACT_OUTLIER_FACTOR
    priced, offers_total, station_ids = 0, 0, set()
    for tid, ship in ships.items():
        q = quotes.get(tid)
        offers = q.offers if q else []
        average, runs_used, offers_used = cheapest_runs_average(offers, want, factor)
        if average is None:
            ContractPrice.objects.filter(ship=ship).delete()
            continue
        cheapest = q.sorted()[:max(offers_used, 5)]
        station_ids.update(o.station_id for o in cheapest if o.station_id)
        ContractPrice.objects.update_or_create(ship=ship, defaults={
            "price_per_run": round(average, 2),
            "lowest_per_run": round(cheapest[0].per_run, 2),
            "runs_used": runs_used,
            "offers_used": offers_used,
            "contracts": len(offers),
            "runs_available": sum(o.runs for o in offers),
            "offers": [o.as_dict() for o in cheapest],
            "snapshot_at": snapshot_at,
            "fetched_at": timezone.now(),
        })
        priced += 1
        offers_total += len(offers)
    if station_ids:
        try:
            from . import industry
            industry.ensure_location_names(station_ids, access_token=None)
        except Exception as exc:  # noqa: BLE001
            logger.info("contract station names not resolved: %s", exc)
    return {"ships": len(ships), "priced": priced, "offers": offers_total, "snapshot_at": snapshot_at}


def fresh_prices(ship_ids=None) -> dict[int, ContractPrice]:
    """{ship type_id: ContractPrice} for rows younger than SHIPYARD_CONTRACT_MAX_AGE_HOURS."""
    cutoff = timezone.now() - timedelta(hours=app_settings.SHIPYARD_CONTRACT_MAX_AGE_HOURS)
    qs = ContractPrice.objects.filter(snapshot_at__gte=cutoff)
    if ship_ids is not None:
        qs = qs.filter(ship_id__in=ship_ids)
    return {c.ship_id: c for c in qs}
