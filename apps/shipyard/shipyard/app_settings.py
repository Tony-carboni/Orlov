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
# (fraction of the LP-store cost incl. tag; 0.05 = 5 %)
SHIPYARD_CORP_BPC_MARKUP = getattr(settings, "SHIPYARD_CORP_BPC_MARKUP", 0.05)

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
