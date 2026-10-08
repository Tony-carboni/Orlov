"""Settings with defaults; override any of them in local.py."""

from django.conf import settings

# Region used for Jita volume history (The Forge)
SHIPYARD_HISTORY_REGION_ID = getattr(settings, "SHIPYARD_HISTORY_REGION_ID", 10000002)

# Days of market history used for the daily-volume average
SHIPYARD_VOLUME_DAYS = getattr(settings, "SHIPYARD_VOLUME_DAYS", 7)

# Pause between external calls in the refresh tasks (seconds)
SHIPYARD_REQUEST_DELAY = getattr(settings, "SHIPYARD_REQUEST_DELAY", 0.15)

# HTTP timeout for external APIs (seconds)
SHIPYARD_HTTP_TIMEOUT = getattr(settings, "SHIPYARD_HTTP_TIMEOUT", 30)

# User agent sent to EVE Ref, Fuzzwork and ESI (be a good citizen)
SHIPYARD_USER_AGENT = getattr(
    settings,
    "SHIPYARD_USER_AGENT",
    "orlov-shipyard/0.1 (auth.orlovfamily.space; The Orlov Family)",
)

# Markup the corp adds when it sells an LP-store blueprint copy on to a member
# (fraction of the LP-store cost incl. tag; 0.10 = 10 %). A manager can give a member
# another rate on the settings page (UserSettings.bpc_markup).
SHIPYARD_CORP_BPC_MARKUP = getattr(settings, "SHIPYARD_CORP_BPC_MARKUP", 0.10)

# The Shipyard's own hostname (second front door, docs/research/06-shipyards-frontend.md).
# Empty = off. Read at request time so tests can override it.
def standalone_host() -> str:
    return (getattr(settings, "SHIPYARD_STANDALONE_HOST", "") or "").strip().lower()


# Skills and standings of the member's character are re-read from ESI when older than this
SHIPYARD_ESI_REFRESH_HOURS = getattr(settings, "SHIPYARD_ESI_REFRESH_HOURS", 24)

# --- Blueprint copies on public contracts (docs/research/06-public-contract-blueprint-prices.md)
# EVE Ref's half-hourly snapshot of every public contract; one download per refresh.
SHIPYARD_CONTRACTS_URL = getattr(
    settings, "SHIPYARD_CONTRACTS_URL",
    "https://data.everef.net/public-contracts/public-contracts-latest.v2.tar.bz2",
)
# Regions whose contracts count (The Forge). Empty list = every region.
SHIPYARD_CONTRACT_REGIONS = getattr(settings, "SHIPYARD_CONTRACT_REGIONS", [10000002])
# Stations whose contracts count (owner, 2026-10-08: Jita 4-4 only). Empty list = every station.
SHIPYARD_CONTRACT_STATIONS = getattr(settings, "SHIPYARD_CONTRACT_STATIONS", [60003760])
# Ship categories priced this way (owner, 2026-10-08): the ones the corp cannot supply.
SHIPYARD_CONTRACT_CATEGORIES = getattr(settings, "SHIPYARD_CONTRACT_CATEGORIES", ["Pirate", "Trig", "Edencom"])
# The figure: average per-run price of the cheapest N runs on offer (owner's rule).
SHIPYARD_CONTRACT_RUNS = getattr(settings, "SHIPYARD_CONTRACT_RUNS", 5)
# Offers dearer than this × the cheapest per-run price are ignored (scams, typos); None = keep all.
SHIPYARD_CONTRACT_OUTLIER_FACTOR = getattr(settings, "SHIPYARD_CONTRACT_OUTLIER_FACTOR", 3.0)
# A contract price older than this is not shown any more ("Price not known").
SHIPYARD_CONTRACT_MAX_AGE_HOURS = getattr(settings, "SHIPYARD_CONTRACT_MAX_AGE_HOURS", 48)

# --- Reprocessing tab (owner's setup, 2026-10-08): T2-rigged Tatara in Sobaseki, all skills V,
# RX-804 implant, 2 % service tax. Yield formula in services/reprocessing.py.
SHIPYARD_REPRO_LOCATION = getattr(settings, "SHIPYARD_REPRO_LOCATION", "Tatara, Sobaseki")
SHIPYARD_REPRO_STRUCTURE = getattr(settings, "SHIPYARD_REPRO_STRUCTURE", "tatara")   # tatara | athanor | other
SHIPYARD_REPRO_RIG = getattr(settings, "SHIPYARD_REPRO_RIG", {"ore": 3, "ice": 3, "moon": 3, "abyssal": 3})  # 0 | 1 (T1) | 3 (T2), per kind
SHIPYARD_REPRO_SECURITY = getattr(settings, "SHIPYARD_REPRO_SECURITY", 0.0)         # 0.0 high, 0.06 low, 0.12 null/WH
SHIPYARD_REPRO_SKILLS = getattr(settings, "SHIPYARD_REPRO_SKILLS", {"reprocessing": 5, "efficiency": 5, "ore": 5})
SHIPYARD_REPRO_IMPLANT = getattr(settings, "SHIPYARD_REPRO_IMPLANT", 0.04)           # RX-801 0.01, RX-802 0.02, RX-804 0.04
SHIPYARD_REPRO_TAX = getattr(settings, "SHIPYARD_REPRO_TAX", 0.02)                   # structure service tax on the output value
SHIPYARD_REPRO_PRICE_POINTS = getattr(settings, "SHIPYARD_REPRO_PRICE_POINTS", [90, 92, 95, 98, 100])
# Where each ore family is mined (not in EVE's data): overrides for the table in services/reprocessing.py,
# {"Family": "highsec" | "lowsec" | "nullsec" | "anomaly"}.
SHIPYARD_ORE_AREAS = getattr(settings, "SHIPYARD_ORE_AREAS", {})

# Cache lifetime for ad-hoc simulations on the detail page (seconds)
SHIPYARD_SIM_CACHE_SECONDS = getattr(settings, "SHIPYARD_SIM_CACHE_SECONDS", 1800)

# Skill effects (EVE rules as of 2026): sales tax -11 % per Accounting level,
# NPC broker fee -0.3 percentage points per Broker Relations level.
SHIPYARD_ACCOUNTING_REDUCTION_PER_LEVEL = getattr(
    settings, "SHIPYARD_ACCOUNTING_REDUCTION_PER_LEVEL", 0.11
)
SHIPYARD_BROKER_RELATIONS_REDUCTION_PER_LEVEL = getattr(
    settings, "SHIPYARD_BROKER_RELATIONS_REDUCTION_PER_LEVEL", 0.003
)
# NPC broker fee: -0.03 percentage points per point of faction standing and -0.02 per
# point of corporation standing with the station owner (unmodified standings).
SHIPYARD_BROKER_FACTION_STANDING_PER_POINT = getattr(
    settings, "SHIPYARD_BROKER_FACTION_STANDING_PER_POINT", 0.0003
)
SHIPYARD_BROKER_CORP_STANDING_PER_POINT = getattr(
    settings, "SHIPYARD_BROKER_CORP_STANDING_PER_POINT", 0.0002
)
