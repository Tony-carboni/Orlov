"""Background refresh. Order: indices → builds → prices → market stats."""

import logging

from celery import chain, shared_task
from django.utils import timezone

from . import app_settings
from .models import (
    BuildSnapshot, Facility, MarketLocation, MaterialType, Ore, OreMarketStats, PriceSnapshot, RefreshRun,
    ScrapItem, Ship, ShipConfig, ShipMarketStats,
)
from .services import bargains, business, contracts, esi, everef, fuzzwork, hangar, industry, ledger, lplog, lpstore, nearbuy, projects, reprocessing, scrapmetal, wallet
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
    """Bill of materials and job cost for every active ship × active facility at the ship's default ME/TE."""
    run = _run("builds")
    n, errors = 0, []
    for fac in Facility.objects.filter(is_active=True):
        for ship in Ship.objects.filter(is_active=True):
            me, te = ship.default_me_te
            try:
                block = everef.manufacturing_cost(
                    ship.type_id,
                    system_id=fac.system_id,
                    structure_type_id=fac.structure_type_id or None,
                    rig_type_ids=fac.rig_type_ids,
                    facility_tax_pct=float(fac.facility_tax),
                    me=me,
                    te=te,
                )
                data = everef.normalise_cost_block(block)
                BuildSnapshot.objects.update_or_create(
                    ship=ship, facility=fac, me=me,
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
    needed.update(_tag_type_ids())
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


def _tag_type_ids() -> set:
    """Tags and other LP-store items that are priced from the market."""
    return {int(t) for t in ShipConfig.objects.exclude(tag_type_id=None).values_list("tag_type_id", flat=True)}


@shared_task
def refresh_prices():
    """Jita aggregates for every hull, every material and every tag, per market location."""
    run = _run("prices")
    type_ids = set(Ship.objects.filter(is_active=True).values_list("type_id", flat=True))
    for mats in BuildSnapshot.objects.values_list("materials", flat=True):
        type_ids.update(int(m["type_id"]) for m in mats)
    type_ids |= _tag_type_ids()
    # the reprocessing tab: every compressed ore and what it gives
    type_ids |= set(Ore.objects.filter(is_active=True).values_list("type_id", flat=True))
    type_ids |= reprocessing.output_type_ids()
    # the scrapmetal tab: every module on the list and its minerals
    type_ids |= scrapmetal.type_ids()
    type_ids |= scrapmetal.output_type_ids()
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
    # buy orders from nearby systems that reach the station (reprocessing and scrapmetal tabs)
    near_station = int(app_settings.SHIPYARD_NEAR_BUY_STATION)
    for loc in MarketLocation.objects.filter(is_active=True, station_id=near_station):
        near_ids = set(Ore.objects.filter(is_active=True).values_list("type_id", flat=True))
        near_ids |= set(ScrapItem.objects.filter(is_active=True).values_list("type_id", flat=True))
        got, errs = nearbuy.refresh(loc, near_ids)
        n += got
        errors.extend(errs[:5])
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
    # the scrapmetal tab: how much of each module Jita trades per day
    for item in ScrapItem.objects.filter(is_active=True):
        try:
            s = esi.volume_stats(region, item.type_id, days)
            item.avg_daily_volume = s["avg_daily_volume"]
            item.avg_price = s["avg_price"]
            item.stats_fetched_at = timezone.now()
            item.save(update_fields=["avg_daily_volume", "avg_price", "stats_fetched_at"])
            n += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{item.name}: {exc}")
            logger.warning("history failed for %s: %s", item, exc)
        polite_pause()
    # the reprocessing tab: how much of each compressed ore Jita trades per day
    for ore in Ore.objects.filter(is_active=True):
        try:
            s = esi.volume_stats(region, ore.type_id, days)
            OreMarketStats.objects.update_or_create(
                ore=ore, defaults={**s, "region_id": region, "fetched_at": timezone.now()}
            )
            n += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{ore.name}: {exc}")
            logger.warning("history failed for %s: %s", ore, exc)
        polite_pause()
    _done(run, not errors, n, "; ".join(errors[:20]))


@shared_task
def refresh_ore_catalog():
    """Compressed ore and ice catalog from EVE Ref (beat entry shipyard_refresh_ore_catalog, weekly)."""
    run = _run("ores")
    try:
        result = reprocessing.import_catalog()
    except Exception as exc:  # noqa: BLE001
        logger.exception("ore catalog refresh failed")
        _done(run, False, 0, str(exc))
        return
    _done(run, True, result["ores"], f"{result['ores']} compressed types in {result['families']} families, {result['materials']} outputs, {result['retired']} retired")


@shared_task
def refresh_scrap_catalog():
    """Modules of the Scrapmetal tab from the owner's list and EVE Ref (beat entry shipyard_refresh_scrap_catalog, weekly)."""
    run = _run("scrap")
    try:
        result = scrapmetal.import_catalog()
    except Exception as exc:  # noqa: BLE001
        logger.exception("scrap catalog refresh failed")
        _done(run, False, 0, str(exc))
        return
    note = f"{result['items']} modules, {result['created']} new, {result['refreshed']} refreshed"
    if result["unresolved"]:
        note += "; not found in EVE: " + ", ".join(result["unresolved"])
    if result["errors"]:
        note += "; errors: " + "; ".join(result["errors"][:10])
    _done(run, not result["errors"] and not result["unresolved"], result["items"], note)


@shared_task
def refresh_corp_projects():
    """The executor corp's projects into our snapshots (beat entry shipyard_refresh_corp_projects, hourly)."""
    run = _run("projects")
    try:
        result = projects.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning("corp projects refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, True, result["projects"],
          f"{result['projects']} projects, {result['snapshots']} new snapshots, {result['contributions']} contribution rows, {result['missing']} gone")
    # the executor corp's journal and market transactions, for the history graphs on the Corp projects tab (0.14.0)
    run = _run("ledger")
    try:
        result = ledger.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning("corp ledger refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, True, result["journal"] + result["transactions"], f"{result['journal']} journal entries, {result['transactions']} market transactions")


@shared_task
def refresh_corp_industry_jobs():
    """The production corp's industry jobs into CorpIndustryJob (beat entry shipyard_refresh_corp_industry_jobs, hourly)."""
    run = _run("corp_jobs")
    try:
        result = business.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning("corp industry jobs refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, True, result["added"], f"{result['added']} new jobs, {result['updated']} updated, {result['total']} kept")


@shared_task
def refresh_hangar():
    """The corporation's hangars from EVE, for the goods held on the Finance tab (beat entry shipyard_refresh_hangar, hourly)."""
    run = _run("hangar")
    try:
        result = hangar.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning("hangar refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, True, result["rows"], f"{result['types']} item types in {result['rows']} hangar rows, read with {result['character']}")


@shared_task
def snapshot_lp():
    """Every character's loyalty points per NPC corporation, the changes kept as the LP log (beat entry shipyard_lp_snapshots, hourly)."""
    run = _run("lp_snapshots")
    try:
        result = lplog.snapshot()
    except Exception as exc:  # noqa: BLE001
        logger.warning("LP snapshot failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    message = f"{result['read']} of {result['characters']} characters read, {result['written']} changes logged"
    if result["errors"]:
        message += "; " + "; ".join(result["errors"][:5])
    _done(run, result["read"] > 0 or not result["characters"], result["written"], message)


@shared_task
def refresh_corp_wallet():
    """The structure corp's wallet journal into our ledger (beat entry shipyard_refresh_corp_wallet, hourly)."""
    run = _run("wallet")
    try:
        result = wallet.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning("corp wallet refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, True, result["added"], f"{result['added']} new entries, {result['total']} in the ledger, {result['divisions']} divisions")
    try:
        from .services import books
        books.flag_outside_master()  # owner's rule (2026-10-25): a project funded from any other wallet is flagged to him
    except Exception as exc:  # noqa: BLE001
        logger.warning("outside-master flag: %s", exc)


@shared_task
def refresh_lp_store():
    """The LP store's offers, Jita prices and daily volumes (beat entry shipyard_refresh_lp_store, daily)."""
    run = _run("lp_store")
    try:
        offers = lpstore.refresh_offers()
        prices = lpstore.refresh_prices()
        volumes = lpstore.refresh_volumes()
    except Exception as exc:  # noqa: BLE001
        logger.warning("LP store refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, not volumes["errors"], offers["offers"],
          f"{offers['offers']} offers ({offers['gone']} gone), {prices['types']} types priced, {volumes['types']} volumes; " + "; ".join(volumes["errors"][:10]))


@shared_task
def refresh_lp_prices():
    """Jita prices of the LP store's types only (beat entry shipyard_refresh_lp_prices, hourly)."""
    run = _run("lp_prices")
    try:
        result = lpstore.refresh_prices()
    except Exception as exc:  # noqa: BLE001
        logger.warning("LP price refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, True, result["types"], f"{result['types']} types priced")


@shared_task
def refresh_contract_prices():
    """Blueprint copy prices for pirate/Trig/EDENCOM hulls from EVE Ref's public-contract snapshot.

    Beat entry: shipyard_refresh_contract_prices (hourly). One 6 MB download, no ESI calls.
    """
    run = _run("contracts")
    try:
        result = contracts.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.exception("contract price refresh failed")
        _done(run, False, 0, str(exc))
        return
    _done(run, True, result.get("priced", 0),
          f"{result.get('priced', 0)} of {result.get('ships', 0)} ships priced from {result.get('offers', 0)} contracts, "
          f"snapshot {result.get('snapshot_at')}")


@shared_task
def refresh_industry():
    """Jobs, blueprints and assets of every character known to the industry page.

    Beat entry: shipyard_refresh_industry (every 30 minutes). Each section is only read
    when it is stale, so the half-hourly run touches jobs; blueprints and assets 4× a day.
    """
    run = _run("industry")
    try:
        done, failed = industry.sync_all()
        _done(run, failed == 0, done, f"{failed} characters with errors" if failed else "")
    except Exception as exc:  # noqa: BLE001
        logger.exception("industry refresh failed")
        _done(run, False, 0, str(exc))


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


@shared_task
def books_check_periods():
    """Hourly: open a new Finance reporting period when the alliance site has a newer State of the Alliance post."""
    from .services import books
    run = _run("books_periods")
    try:
        period = books.check_posts()
    except Exception as exc:  # noqa: BLE001
        logger.warning("books periods: %s", exc)
        _done(run, False, 0, str(exc)[:300])
        return
    _done(run, True, 1 if period else 0, f"period opened: {period.source}" if period else "no newer State of the Alliance post")


@shared_task
def refresh_market_history():
    """Bargains: the new or completed days of EVE Ref's market-history archive, then the year per type, names and market
    groups (beat entry shipyard_refresh_market_history, daily 13:30 UTC; EVE Ref publishes a day the next morning)."""
    run = _run("history")
    try:
        r = bargains.sync_history()
        types = bargains.compute_stats()
        named = bargains.fill_names()
        grouped = bargains.fill_groups()
    except Exception as exc:  # noqa: BLE001
        logger.warning("market history refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, True, types, f"{r['downloaded']} day archives fetched ({r['days']} kept), {types} types, {named} named, {grouped} grouped")


@shared_task
def refresh_bargain_prices():
    """Bargains: Jita 4-4 prices of every type that traded in the last 30 days (beat entry shipyard_refresh_bargain_prices, every two hours)."""
    run = _run("bargain_prices")
    try:
        r = bargains.refresh_prices()
    except Exception as exc:  # noqa: BLE001
        logger.warning("bargain price refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, True, r["types"], f"{r['types']} of {r['asked']} types priced")
