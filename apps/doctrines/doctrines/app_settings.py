"""Settings of the Doctrines plugin, all with defaults; override in conf/local.py."""

from django.conf import settings

# The doctrines' own hostname, for example "doctrines.orlovfamily.space". "" keeps the pages on
# auth's host only (runbook 16 B releases with "", C switches it on).
DOCTRINES_HOST = getattr(settings, "DOCTRINES_HOST", "")

# Market for the fitting prices: Fuzzwork station aggregates, lowest sell. Jita IV-4.
DOCTRINES_MARKET_STATION_ID = getattr(settings, "DOCTRINES_MARKET_STATION_ID", 60003760)
DOCTRINES_MARKET_NAME = getattr(settings, "DOCTRINES_MARKET_NAME", "Jita IV-4")

# Prices older than this are refreshed by the hourly task; the page never calls the market itself.
DOCTRINES_PRICE_MAX_AGE_HOURS = getattr(settings, "DOCTRINES_PRICE_MAX_AGE_HOURS", 2)

# Insurance level used for the net payout column.
DOCTRINES_INSURANCE_LEVEL = getattr(settings, "DOCTRINES_INSURANCE_LEVEL", "Platinum")

# The brand shown in the top bar of the standalone pages.
DOCTRINES_BRAND = getattr(settings, "DOCTRINES_BRAND", "Orlov Doctrines")


def host() -> str:
    """Read at call time (not import time), so tests can override the setting."""
    return (getattr(settings, "DOCTRINES_HOST", "") or "").strip().lower()

# SRP (owner, 2026-10-18): the corporation whose wallet pays, its SRP wallet division, and the alliances
# whose pilots may ask (empty = no check; the kill feed's alliance list is used as well).
DOCTRINES_SRP_CORP_ID = getattr(settings, "DOCTRINES_SRP_CORP_ID", 98843356)   # Orlov Arms International
DOCTRINES_SRP_WALLET_DIVISION = getattr(settings, "DOCTRINES_SRP_WALLET_DIVISION", 2)
DOCTRINES_SRP_ALLIANCE_IDS = getattr(settings, "DOCTRINES_SRP_ALLIANCE_IDS", [])
