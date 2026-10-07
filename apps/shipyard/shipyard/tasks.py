"""Background refresh. Order: indices → builds → prices → market stats."""

import logging

from celery import chain, shared_task
from django.utils import timezone

from . import app_settings
from .models import (
    BuildSnapshot, Facility, MarketLocation, MaterialType, PriceSnapshot, RefreshRun, Ship,
    ShipMarketStats,
)
from .services import esi, everef, fuzzwork
from .services.http import polite_pause

logger = logging.getLogger(__name__)


def _run(step):
    return RefreshRun.objects.create(step=step)


def _done(run, ok, items=0, message=""):
    run.finished_at = timezone.now()
    run.ok = ok
    run.items = items
    run.message = message[:2000]
    run.save()


@shared_task
def refresh_facility_indices():
    run = _run("indices")
    try:
        indices = esi.industry_indices()
        n = 0
        for fac in Facility.objects.filter(is_active=True):
            if fac.system_id in indices:
                fac.manufacturing_index = indices[fac.system_id]
                fac.index_updated_at = timezone.now()
                fac.save(update_fields=["manufacturing_index", "index_updated_at"])
                n += 1
        _done(run, True, n)
    except Exception as exc:  # noqa: BLE001
        logger.exception("indices refresh failed")
        _done(run, False, 0, str(exc))


@shared_task
def refresh_builds():
    """ME 0 bill of materials and job cost for every active ship × active facility."""
    run = _run("builds")
    n, errors = 0, []
    for fac in Facility.objects.filter(is_active=True):
        for ship in Ship.objects.filter(is_active=True):
            try:
                block = everef.manufacturing_cost(
                    ship.type_id,
                    system_id=fac.system_id,
                    structure_type_id=fac.structure_type_id or None,
                    rig_type_ids=fac.rig_type_ids,
                    facility_tax_pct=float(fac.facility_tax),
                )
                data = everef.normalise_cost_block(block)
                BuildSnapshot.objects.update_or_create(
                    ship=ship, facility=fac, me=0,
                    defaults={**data, "fetched_at": timezone.now()},
                )
                n += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{ship.name}@{fac.name}: {exc}")
                logger.warning("build refresh failed for %s at %s: %s", ship, fac, exc)
            polite_pause()
    _ensure_material_names()
    _done(run, not errors, n, "; ".join(errors[:20]))


def _ensure_material_names():
    """Fill the MaterialType cache for any material we have not seen yet."""
    known = set(MaterialType.objects.values_list("type_id", flat=True))
    needed = set()
    for mats in BuildSnapshot.objects.values_list("materials", flat=True):
        needed.update(int(m["type_id"]) for m in mats)
    for tid in sorted(needed - known):
        try:
            t = everef.get_type(tid)
            MaterialType.objects.update_or_create(
                type_id=tid,
                defaults={"name": everef.type_name(t), "volume": float(t.get("packaged_volume") or t.get("volume") or 0)},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("material name lookup failed for %s: %s", tid, exc)
        polite_pause()


@shared_task
def refresh_prices():
    """Jita aggregates for every hull and every material, per market location."""
    run = _run("prices")
    type_ids = set(Ship.objects.filter(is_active=True).values_list("type_id", flat=True))
    for mats in BuildSnapshot.objects.values_list("materials", flat=True):
        type_ids.update(int(m["type_id"]) for m in mats)
    n, errors = 0, []
    for loc in MarketLocation.objects.filter(is_active=True):
        try:
            agg = fuzzwork.station_aggregates(loc.station_id, type_ids)
            now = timezone.now()
            for tid, a in agg.items():
                PriceSnapshot.objects.update_or_create(type_id=tid, location=loc, defaults={**a, "fetched_at": now})
                n += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{loc.name}: {exc}")
            logger.exception("price refresh failed for %s", loc)
    _done(run, not errors, n, "; ".join(errors))


@shared_task
def refresh_market_stats():
    """7-day average daily volume per ship from ESI history."""
    run = _run("stats")
    n, errors = 0, []
    region = app_settings.SHIPYARD_HISTORY_REGION_ID
    days = app_settings.SHIPYARD_VOLUME_DAYS
    for ship in Ship.objects.filter(is_active=True):
        try:
            s = esi.volume_stats(region, ship.type_id, days)
            ShipMarketStats.objects.update_or_create(
                ship=ship, defaults={**s, "region_id": region, "fetched_at": timezone.now()}
            )
            n += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ship.name}: {exc}")
            logger.warning("history failed for %s: %s", ship, exc)
        polite_pause()
    _done(run, not errors, n, "; ".join(errors[:20]))


@shared_task
def refresh_all():
    """Full refresh, in order. Beat entry: shipyard_refresh_all."""
    chain(
        refresh_facility_indices.si(),
        refresh_builds.si(),
        refresh_prices.si(),
        refresh_market_stats.si(),
    ).apply_async()


@shared_task
def refresh_prices_and_stats():
    """Cheaper refresh for a shorter beat interval (no EVE Ref calls)."""
    chain(refresh_prices.si(), refresh_market_stats.si()).apply_async()
