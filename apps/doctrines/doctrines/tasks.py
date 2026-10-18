"""Background refreshes: fitting prices (hourly) and the insurance table (daily)."""

import logging

from celery import shared_task

from .models import RefreshRun
from .services import insurance, prices

logger = logging.getLogger(__name__)


def _run(step):
    return RefreshRun.objects.create(step=step)


def _done(run, ok, items=0, message=""):
    run.ok = ok
    run.items = items
    run.message = message[:300]
    run.save(update_fields=["ok", "items", "message"])


@shared_task
def refresh_prices():
    """Jita prices of every type in a fitting (beat entry doctrines_refresh_prices, hourly)."""
    run = _run("prices")
    try:
        result = prices.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning("doctrines price refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, True, result["updated"], f"{result['updated']} of {result['types']} types priced")


@shared_task
def refresh_insurance():
    """EVE's insurance table (beat entry doctrines_refresh_insurance, daily)."""
    run = _run("insurance")
    try:
        result = insurance.refresh()
    except Exception as exc:  # noqa: BLE001
        logger.warning("doctrines insurance refresh failed: %s", exc)
        _done(run, False, 0, str(exc))
        return
    _done(run, True, result["hulls"], f"{result['hulls']} hulls at {result['level']}")


@shared_task
def srp_match_payments():
    """Hourly: mark SRP requests paid when the SRP wallet's journal shows the transfer with the kill id."""
    from .services import srp

    run = _run("srp_payments")
    try:
        result = srp.match_payments()
    except Exception as exc:  # noqa: BLE001
        logger.warning("SRP payments: %s", exc)
        _done(run, False, message=str(exc)[:300])
        return
    _done(run, bool(result.get("ok")), items=int(result.get("matched", 0)), message=result.get("message", "")[:300])
