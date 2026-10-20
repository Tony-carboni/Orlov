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

## Corp projects history (0.14.0)

The Corp projects tab draws seven graphs from one event list built in `services/projectbooks.py`; the interval (days, weeks, every N days) and the date range change in the browser (`static/shipyard/projects_charts.js`). Payouts are each member's contribution growth between two hourly reads times the reward per unit; contributions the first read found are spread over the days before and marked estimated. Funding and refunds come from the executor corp's wallet journal, sales from its market transactions, both copied hourly by `services/ledger.py` (token: a corp character with `esi-wallet.read_corporation_wallets.v1`). Sales are matched first in, first out to the deliveries they came from; an ore or ice the corp never sold as delivered is matched through its reprocessing outputs, its cost split by their Jita buy value.

## LP conversion (0.15.0)

The LP conversion tab lists every offer of a militia's loyalty point store (`SHIPYARD_LP_STORE_CORP_ID`, State Protectorate by default; ESI's public `/loyalty/stores/{corp}/offers/`) valued at Jita: the items at Jita lowest sell, minus the store's ISK charge, minus the items you hand in at Jita lowest sell, gives the net ISK per LP, plus the rate after your sales tax and broker fee, Jita's daily volume and the depth of the sell orders. A blueprint copy has no market price; its row shows what a copy must fetch to reach `SHIPYARD_LP_TARGET_ISK_PER_LP` (900). `services/lpstore.py`; offers and volumes refresh daily (`shipyard_refresh_lp_store`), prices hourly (`shipyard_refresh_lp_prices`); managers have a Refresh button.

## Member shipyards (0.16.0)

For the owner (`shipyard.manage_shipyard`): the **Member shipyards** tab shows the ship dashboard as a new member sees it, from `services.board.member_settings()` (an unsaved default settings row: the corp's default facility and market, no character, the corp's blueprint markup, no own blueprints or prices). Nothing on it is saved; `?facility=<pk>` previews another facility.

## Finance (0.17)

The directors' balance sheet against the owner's working budget (`services/books.py`), at `/shipyard/finance/` for `manage_shipyard` or `books_access`, with a PDF on demand (`services/books_pdf.py`, reportlab). The baseline and stock batches are edited in the admin (books baseline, stock batches). Settings: `SHIPYARD_BOOKS_DIVISIONS` (default 1 to 6; 7 is the owner's), `SHIPYARD_BOOKS_STRUCTURE_TRANSFER` (reason pattern of structure income moved in, default `raitaru`), `SHIPYARD_BOOKS_FUEL` (structures, blocks per hour, sponsored).
