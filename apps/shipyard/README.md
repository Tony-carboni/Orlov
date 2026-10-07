# Shipyard — Alliance Auth plugin

T1 / faction ship-building profit dashboard for The Orlov Family. Lives in the auth menu as **Shipyard**.

## What it does
- **Dashboard**: every buildable T1, navy, pirate, Triglavian, EDENCOM and ORE hull up to battleship (plus barges and haulers), with net profit, margin, Jita sell price, sales tax, input cost, 7-day daily volume, market depth (days of stock on Jita sell orders), blueprint cost and build time. Filters by type and hull size, sortable, row click → detail.
- **Ship detail**: full bill of materials with Jita prices and m³, cost waterfall, and a **simulation panel** (ME 0–10, TE, facility, blueprint and tag cost, LP pricing on/off) that never touches the dashboard numbers. "Copy multibuy" puts the material list on the clipboard.
- **My settings** (per member): facility preset (info card with rigs, system index, tax), market location (taxes), skills loaded from a character via ESI or set by hand, optional overrides for sales tax and broker fee, "price blueprints from LP" switch.
- **Blueprints & LP** (managers): blueprint price per run, tag/extra cost, LP-store offer (LP, ISK, runs) per ship; ISK-per-LP per faction.

## Data sources (all public, no EVE login)
- EVE Ref industry cost API — bill of materials (ME/structure/rig adjusted), job cost, build time.
- Fuzzwork station aggregates — Jita 4-4 lowest sell, sell volume and order count for hulls and materials.
- ESI — regional market history (volume), industry system cost indices, and (authed) character skills.
- EVE Ref reference data — ship catalog and material names.

## Calculation
Net profit = sell price (Jita lowest sell) − materials (Jita lowest sell × ME-adjusted quantity) − job cost (EIV × (system index + SCC 4 %) + facility tax) − blueprint per run − tags − sales tax − broker fee.
Sales tax = base 7.5 % × (1 − 0.11 × Accounting). Broker fee (NPC station) = 3 % − 0.3 pp × Broker Relations − 0.03 pp × faction standing − 0.02 pp × corporation standing with the station's owners (unmodified standings of the skills character, loaded together with the skills). Both can be overridden per member. Build times assume industry skills V on the dashboard; the simulation uses the member's skills.

## Install (Alliance Auth, Docker)
1. Add to `conf/requirements.txt` (pin the commit):
   `orlov-shipyard @ https://github.com/Tony-carboni/Orlov/archive/<commit-sha>.tar.gz#subdirectory=apps/shipyard`
2. `local.py`: `INSTALLED_APPS += ["shipyard"]` and the beat entries from `deploy/conf/local.py.append` (full refresh every 6 h, prices + volumes hourly).
3. Build, `up -d`, `restart nginx`, `migrate`, `collectstatic`.
4. `manage.py shipyard_load_ships` (catalog + default facility/market/LP factions), then `manage.py shipyard_refresh` (first data load, ~3 min).
5. Permissions: `shipyard | general | Can access the Shipyard dashboard` to the groups that may see it; `Can edit blueprint prices…` to managers. Superusers see it without any grant.

## Settings (optional, local.py)
`SHIPYARD_HISTORY_REGION_ID` (10000002), `SHIPYARD_VOLUME_DAYS` (7), `SHIPYARD_REQUEST_DELAY` (0.15 s), `SHIPYARD_SIM_CACHE_SECONDS` (1800), `SHIPYARD_USER_AGENT`.

## Management commands
- `shipyard_load_ships [--no-seed]` — rebuild the catalog from EVE Ref (new hulls appear; existing rows keep their active flag and config).
- `shipyard_refresh [--prices-only]` — run the refresh synchronously.

## Tests
From `apps/shipyard` with a scratch settings module containing the app: `python -m django test shipyard`.
