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
# --- Scrapmetal tab (owner's setup, 2026-10-08): modules reprocessed at 0 % tax in the Isikano Raitaru.
# Only the Scrapmetal Processing skill matters (50 % + 2 %/level); the member's level is used once a
# character is loaded, the default before that.
SHIPYARD_SCRAP_LOCATION = getattr(settings, "SHIPYARD_SCRAP_LOCATION", "Raitaru, Isikano")
SHIPYARD_SCRAP_TAX = getattr(settings, "SHIPYARD_SCRAP_TAX", 0.0)
SHIPYARD_SCRAP_SKILL_DEFAULT = getattr(settings, "SHIPYARD_SCRAP_SKILL_DEFAULT", 5)
SHIPYARD_SCRAP_PRICE_POINTS = getattr(settings, "SHIPYARD_SCRAP_PRICE_POINTS", [90, 92, 95, 98, 100])

# Buy orders that reach the market station from nearby systems count as well (owner, 2026-10-09):
# {system id: jumps from the station}. A buy order in one of these systems counts when its range
# covers that many jumps (or the region); orders in the station's own system count with any range
# but "station" (those only at the station itself). Used for the reprocessing and scrapmetal tabs.
SHIPYARD_NEAR_BUY_SYSTEMS = getattr(settings, "SHIPYARD_NEAR_BUY_SYSTEMS", {30000142: 0, 30000144: 1})  # Jita, Perimeter
SHIPYARD_NEAR_BUY_STATION = getattr(settings, "SHIPYARD_NEAR_BUY_STATION", 60003760)  # Jita 4-4

# --- LP conversion tab (owner, 2026-10-19): a militia's loyalty point store valued at Jita --------
SHIPYARD_LP_STORE_CORP_ID = getattr(settings, "SHIPYARD_LP_STORE_CORP_ID", 1000180)  # State Protectorate (Caldari militia)
SHIPYARD_LP_STORE_NAME = getattr(settings, "SHIPYARD_LP_STORE_NAME", "State Protectorate")
SHIPYARD_LP_TARGET_ISK_PER_LP = getattr(settings, "SHIPYARD_LP_TARGET_ISK_PER_LP", 900)  # the rate a blueprint copy must reach

# --- Structure income tab (owner, 2026-10-14): the structure corp's wallet journal ---------
SHIPYARD_STRUCTURE_CORP_ID = getattr(settings, "SHIPYARD_STRUCTURE_CORP_ID", 98635713)  # Gewoon voor structures (GWON)
SHIPYARD_WALLET_SCOPES = getattr(settings, "SHIPYARD_WALLET_SCOPES", [
    "esi-wallet.read_corporation_wallets.v1",
    "esi-corporations.read_divisions.v1",
])
# Journal ref types that count as structure income (positive amounts); empty list = every positive entry.
SHIPYARD_INCOME_REF_TYPES = getattr(settings, "SHIPYARD_INCOME_REF_TYPES", [
    "industry_job_tax", "reprocessing_tax", "brokers_fee", "office_rental_fee",
    "jump_clone_installation_fee", "structure_gate_jump", "docking_fee", "planetary_import_tax", "planetary_export_tax",
])

# --- Corp projects tab (owner, 2026-10-14): the executor corp's projects, snapshotted hourly ------
SHIPYARD_PROJECTS_CORP_ID = getattr(settings, "SHIPYARD_PROJECTS_CORP_ID", 98843356)  # Orlov Arms International (OARMI)
SHIPYARD_PROJECTS_SCOPES = getattr(settings, "SHIPYARD_PROJECTS_SCOPES", ["esi-corporations.read_projects.v1"])

# --- My business tab (owner, 2026-10-14): production = the production corp's industry jobs ----
SHIPYARD_PRODUCTION_CORP_ID = getattr(settings, "SHIPYARD_PRODUCTION_CORP_ID", 98843356)  # Orlov Arms International (OARMI)
SHIPYARD_PRODUCTION_SCOPES = getattr(settings, "SHIPYARD_PRODUCTION_SCOPES", ["esi-industry.read_corporation_jobs.v1"])

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

# --- Scopes asked of a character at the front door (owner, 2026-10-14) --------------------
# True: every scope EVE offers (constants.ALL_ESI_SCOPES) plus the Shipyard's own set, so no
# later app or scope change needs another login. False: only the Shipyard's set (Member Audit's 33).
SHIPYARD_REQUEST_ALL_SCOPES = getattr(settings, "SHIPYARD_REQUEST_ALL_SCOPES", True)
SHIPYARD_EXTRA_SCOPES = list(getattr(settings, "SHIPYARD_EXTRA_SCOPES", []))  # more scopes to ask for, on top

# Reprocessing tab: the alliance buyback price as a share of the reprocessing output value (the "BB" column).
SHIPYARD_BUYBACK_SHARE = float(getattr(settings, "SHIPYARD_BUYBACK_SHARE", 0.85))

# --- Finance tab (owner, 2026-10-20): the directors' balance sheet ----------------------------------
SHIPYARD_BOOKS_DIVISIONS = getattr(settings, "SHIPYARD_BOOKS_DIVISIONS", [1, 2, 3, 4, 5, 6])  # 7 is the owner's shared wallet
# A deposit whose reason matches this is structure income moved into the corporation
SHIPYARD_BOOKS_STRUCTURE_TRANSFER = getattr(settings, "SHIPYARD_BOOKS_STRUCTURE_TRANSFER", r"raitaru")
# Fuel need of the online service modules, per structure
SHIPYARD_BOOKS_FUEL = getattr(settings, "SHIPYARD_BOOKS_FUEL", [
    {"name": "Orlov Family Facilities (Raitaru)", "blocks_per_hour": 28, "sponsored": True},
    {"name": "Orlov Mining Facility I (Athanor, Piekura)", "blocks_per_hour": 4},
    {"name": "Orlov Mining Facility II (Athanor, Saatuban)", "blocks_per_hour": 4},
])
