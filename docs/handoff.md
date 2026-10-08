# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-07 (18:00 UTC) — laptop session → desktop session (owner continues tomorrow)

**State of play in one paragraph.** The Shipyard is at **0.3.0** on the server (commit `07f5edb` pinned), with three releases today from this session: 0.1.7 (standings in the broker fee), 0.2.0 (the own front door, switched off), 0.3.0 (My industry page, own blueprints in the numbers, corp/alliance scopes). The front door `shipyards.orlovfamily.space` is **built but closed**: it waits for the owner's DNS record and proxy host (runbook 14 A), then one settings flip (14 C). Everything below is in the repo; the server matches `deploy/`.

### What the owner decided today (laptop session)
- **Front door:** Family Member **and** Family Friend may use it; characters grant **everything** (the 33 Member Audit scopes); it runs on the existing server (headroom checked).
- **My industry:** a full dashboard of jobs and assets; a Family Member sees **only their own characters**, a **Corp Director** everyone in their corp, an **Alliance Director** everyone in the alliance.
- **Pirate / Trig / EDENCOM blueprints:** keep showing the profit **without** the blueprint ("public contracts only", marker `no BPC`); do **not** subtract a typed price. Reason: contract prices move too fast to maintain; the owner checked that sheet profit + sheet BPC = app profit without BPC (Vindicator: 52.4 M + 23 M ≈ 71.4 M after the small timing and tax differences) and is satisfied. Members judge a copy's price themselves with the blueprint-cost field on the ship page. Wording wish for the next release: the label should read **"only on public contracts"** (today: "public contracts only"); no rebuild for that alone.
- **Standings:** yes, factor them in (done in 0.1.7). Sales tax is not affected by standings, only the broker fee.

### Server state after this session
- Containers: all 11 up, Shipyard 0.3.0 installed, site 200, bot found its three boards after each `up -d`, 0 errors in the logs.
- `conf/local.py` is 244 lines. Appended today, in this order: the "Shipyards front door" block with `SHIPYARD_STANDALONE_HOST = ""` (door closed), `MIDDLEWARE += ["shipyard.middleware.StandaloneHostMiddleware"]`, `SESSION_COOKIE_DOMAIN`/`CSRF_COOKIE_DOMAIN = ".orlovfamily.space"`, `CSRF_TRUSTED_ORIGINS += ["https://shipyards.orlovfamily.space"]`; then the beat entry `shipyard_refresh_industry` (crontab minute 5,35). `deploy/conf/local.py.append` has the same blocks (with the real host name in the template).
- Migrations applied: shipyard 0003 (market owners, standings) and 0004 (industry tables, two permissions). No pending migration.
- Permissions: `shipyard.basic_access` on the **states** Family Member (11 accounts) and Family Friend (1); `view_corp_industry` on group Corp Director (3 members); `view_alliance_industry` on group Alliance Director (tony). The runbook-13-D group grants from earlier are superseded by the state grants.
- Owner's settings: skills and 83 standings of Catherine Frey stored; broker fee at Jita 1.461 %.
- Industry data already read for tony's 10 characters (first read happened in the dry run); the half-hourly task keeps it fresh for everyone who opens the page once.
- Backups in `~/backups`: `aa-db-2026-10-07-1638/1701/1744.sql.gz`, `requirements.txt.pre-0.1.7/0.2.0/0.3.0`, `local.py.pre-0.2.0/0.3.0`, `local.py.pre-reinforce-hour` etc. from the bot work.
- Discord: System Messages Channel moved to `#public-chat` on 2026-10-06; otherwise untouched today.

### Code map of what changed today (apps/shipyard/shipyard)
- `middleware.py` — host routing for the front door (`StandaloneHostMiddleware`): pass-through prefixes, SSO bounce `/shipyard/go/`, 403 page `no_access.html`, redirect of auth's `/shipyard/…` to the standalone host. Reads `app_settings.standalone_host()` per request.
- `services/characters.py` — `full_scopes()` (Member Audit's `Character.esi_scopes()` or `constants.FULL_SCOPES`), `token_for()`, `register_in_memberaudit()`, `load_character()` (skills + standings, clears manual overrides), `ensure_fresh()` (daily), `choices()` for the picker.
- `services/industry.py` — `sync_user()` / `sync_all()` / `sync_character()` (jobs + slot skills every 30 min, blueprints and assets every 6 h; assets kept for `relevant_type_ids()` only and rolled up with `root_location()`), name caches `ensure_type_names()` (into `MaterialType`) and `ensure_location_names()` (`LocationName`; structures via the character's token, unknown ones retried after a day), `owned_blueprints()`, `allowed_scopes()` / `visible_syncs()`, `overview(user, scope)` (a finished job EVE still calls "active" counts as ready).
- `services/board.py` — `dashboard_rows()` uses the member's best own blueprint (ME/TE) through `simulate_build()` for at most 25 ships per render; `BoardRow.owned_bp`.
- `services/esi.py` — `_authed()`, `_authed_pages()` (X-Pages, cap 20), `character_skill_levels()`, `character_industry_jobs()`, `character_blueprints()`, `character_assets()`, `structure_info()`, `character_standings()`.
- `services/pricing.py` — broker fee with standings (`SHIPYARD_BROKER_FACTION_STANDING_PER_POINT` 0.0003, `…CORP…` 0.0002).
- `views.py` — `_context()` picks the frame; `use_character()` (POST from the picker; SSO once with all scopes, session key `shipyard_sso_pending`; falls back to the character the member actually logged in with), `go()`, `industry_view()` (GET `?scope=own|corp|alliance`, POST = refresh own characters), `ship_detail()` starts the simulation at the own blueprint's ME/TE. `load_skills` and the manual skill/tax inputs are gone.
- `models.py` — `MarketLocation.owner_corporation_id/owner_faction_id`, `UserSettings.standings/standings_fetched_at/standing_with()`, `CharacterSync`, `IndustryJob`, `CharacterBlueprint`, `CharacterAsset`, `LocationName`; `General` permissions ×4.
- `tasks.py` — `refresh_industry` (beat :05/:35). `constants.py` — `FULL_SCOPES`, `ACTIVITIES`, `SLOT_SKILLS`. `templatetags` — `shipyard_logout_url`, `remaining`.
- Templates — `frame_standalone.html` / `frame_auth.html` (base.html extends the `frame` variable), `settings.html` (character picker), `industry.html` (scope buttons, strip, jobs, blueprints, stock), `no_access.html`; dashboard badge "your BPO ME10"; detail header shows the own blueprint.
- Tests: 47 (`test_pricing.py`, `test_board.py`, `test_frontdoor.py`, `test_industry.py`).

### Useful patterns learned today (for the desktop session)
- **Test and dry-run the working copy before building:** `tar` `apps/shipyard` to `~/shipyard-dev` on the server (strip CR), then `docker compose run --rm --no-deps -T -v ~/shipyard-dev/apps/shipyard:/dev/shipyard:ro --entrypoint sh allianceauth_gunicorn -c '... PYTHONPATH=/dev/shipyard ...'`: `manage.py check`, the unit tests with the SQLite settings file in `/tmp`, `makemigrations --check`, and a Django test `Client` with `force_login` and `HTTP_HOST` for live page renders. Migrations can be applied from there too (additive ones are safe before the build).
- Release = runbook 13 C: backup → copy `requirements.txt` → `sed` the SHA → build → throwaway checks → migrate → `up -d` → `restart nginx` → `collectstatic` → verify → docs.
- Python patch scripts for docs must normalise CRLF before matching and be re-runnable; run them with `python -X utf8` from a file (heredocs mangled the en dashes and `\U` in Windows paths).
- The sheet: `OneDrive/EVE/ships dashboard v3.2.xlsx` on the laptop; copy it out of OneDrive before reading with openpyxl.

### Open items, in order
1. ~~Owner (runbook 14 A)~~ **done 2026-10-08** (DNS record and proxy host with certificate; the new host served auth's dashboard).
2. ~~Local session (14 C)~~ **done 2026-10-08 by the desktop session:** `SHIPYARD_STANDALONE_HOST = "shipyards.orlovfamily.space"` set, containers restarted, redirect chain verified (visitor → `/shipyard/` → SSO login → EVE; auth's `/shipyard/` → new host). **Open: the owner's browser check, runbook 14 D.** Original text of this item: set `SHIPYARD_STANDALONE_HOST = "shipyards.orlovfamily.space"` in `conf/local.py` (sed on the existing line), `docker compose restart allianceauth_gunicorn allianceauth_worker allianceauth_worker_services allianceauth_beat`, then from the server: `curl -sI https://shipyards.orlovfamily.space/` → 302 to `https://auth.orlovfamily.space/sso/login?next=/shipyard/go/`, and `curl -sI https://auth.orlovfamily.space/shipyard/` → 302 to the new host. Then the owner does 14 D.
3. **Owner checks:** `#structure-board`/`#moon-board`/`#zkillboard`/`#jf-gank-board` looks; the 3 Nov reinforcement date in game; Go Browns' alliance join (then remove GB44 from the Family Member state's corporations); profile names for the structure board; "refresh the founders" once new Family Members are in.
4. **Shipyard 0.3.1–0.3.3 released 2026-10-08 by the desktop session** (search box, no toggles, dark theme, swappable facility card, settings = character only, markup 10 % + manager override set to 0 for tony, Consortium hulls off, Isikano tax 0.1 %; details in runbook 13 C). **0.3.4 released 2026-10-07 20:15 UTC by the desktop session:** Perseverance set to public contracts only via a per-ship policy table (`BPC_POLICY_BY_NAME`), no migration, 48 tests. **0.4.0 released 2026-10-08 08:20 UTC by the desktop session:** right-click a Blueprint cell on the dashboard to type your own price for the copy; it replaces the corp's figure in your own numbers (also on the ship page), marked `yours`, until cleared. This supersedes the earlier "do not subtract a typed price" for pirate hulls: a price the member types for themselves is subtracted, the corp-wide policy is unchanged. Migration 0006 applied, 49 tests. **0.4.1 released 2026-10-08 08:40 UTC:** "public contracts only" and "not priced yet" are gone, the cell reads "Price not known" until a value is entered (owner's wording). **0.5.0 released 2026-10-08 08:50 UTC:** Pirate/Trig/EDENCOM blueprint prices come from public contracts (EVE Ref snapshot, hourly beat entry `shipyard_refresh_contract_prices`, migration 0007, 55 tests; owner's rule = average per run of the cheapest five runs on offer in The Forge, outliers above 3× the cheapest ignored; details in runbook 13 C and research doc 06). **0.5.1:** Jita 4-4 contracts only (`SHIPYARD_CONTRACT_STATIONS`); outlier guard kept on the owner's say-so. **0.5.2:** manager Refresh button on the dashboard (queues prices, volumes, contract prices; 5-minute cooldown). Pack contracts count under the rule (a 7-copy Vedmak pack at 39 M made the figure 5.57 M while singles sat at 6.78 M); the owner looked, bought the pack and keeps the rule as is. **0.6.0:** the contract figure moved to its own "Contracts" column, information only; the Blueprint column (own set price, else corp figure, else Price not known) is the only thing in the numbers. **0.6.1:** the Contracts column shows the cheapest per-run price listed and the hover names the contract (ID, issuer, price, copies/runs, ME/TE, title, expiry). The owner cleared his own Vedmak/Drekavac/Rodiva prices himself; 750 k on the 12 base battleships remains. Owner's own-price rows: 750 k per run on the 12 base battleships (set by the desktop session on request), plus Vedmak, Drekavac and Rodiva typed by the owner; own prices win over contract figures. **Next Shipyard release, when there is a reason:** ~~label "only on public contracts"~~ (moot since 0.4.1); ~~navy frigate LP offers~~ (entered 2026-10-08 by the desktop session: 12 navy frigates, 4,000 LP + 2 M ISK, verified in ESI, data only); front-door phase 3 ideas the owner may raise after using phase 2 (for example corp hangar stock, which needs corp roles and the structures token).
5. **Housekeeping:** `~/shipyard-dev` on the server is a scratch copy and can be removed; `tasks.py refresh_industry` logs a `RefreshRun` row "industry" every half hour (admin → Shipyard → Refresh runs).


---

## 2026-10-07 (13:30 UTC) — local session (PC) → cloud session

**Runbook:** `docs/runbooks/13-shipyard-plugin.md` — **section A done; plugin updated to 0.1.1 and the navy cruiser baseline entered (see below).** B (owner, browser) is next.

### Done (local, on the server)
- Pinned commit `233303255d07a90d3314280cc202dc653cc5ff58` (branch head at the time). GitHub serves the archive (146 KB).
- Backup `~/backups/aa-db-2026-10-07-1321.sql.gz`; copies `requirements.txt.pre-shipyard` and `local.py.pre-shipyard` in `~/backups`.
- `conf/requirements.txt` + the `orlov-shipyard @ …/archive/<sha>.tar.gz#subdirectory=apps/shipyard` line; `conf/local.py` + the Shipyard block (byte-identical to `deploy/`, file now 229 lines).
- Build exit 0, pip installed `orlov-shipyard-0.1.0`. Throwaway container: `check` no issues; `migrate shipyard` applied `0001_initial` (12 models). `up -d` recreated gunicorn, beat, the three workers and the bot; nginx restarted; `collectstatic` copied 122 files. Site 200, 11 containers up, bot reloaded all four modules and found its three boards.
- `shipyard_load_ships`: facility "Orlov Raitaru — Isikano" and market "Jita IV-4" created, LP factions seeded, catalog 188 new / 188 total.
- `shipyard_refresh`: RefreshRun rows indices (1 item), builds (174), prices (196), stats (174), all `ok`, no messages. Ship 188 total / 174 active, BuildSnapshot 174, PriceSnapshot 196, ShipMarketStats 174.
- Order differed from the handoff on purpose: requirements and build first, settings block after, so no container could restart on the old image with the new app named (lesson from Day 6).

### Shipyard 0.1.1 and the navy cruiser baseline (local, 2026-10-07 13:40–14:10 UTC)
- Owner's instructions: navy cruiser blueprint cost = 18,000 LP × the faction's ISK/LP + the faction crystal tag at Jita's **lowest sell** (never a median); ISK/LP baseline Amarr 900, Gallente 850, Minmatar 700, Caldari 900; the type filter must allow several types at once.
- Verified in ESI: the four militia LP stores sell every navy cruiser BPC for 18,000 LP + 1 crystal tag, 0 ISK, 1 run (the navy corps' own stores want 100,000 LP). Tag type IDs: True Sansha 17255 (Amarr), Dread Guristas 17244 (Caldari), Shadow Serpentis 17266 (Gallente), Domination 17223 (Minmatar).
- Plugin change (commit `48f73d4`, version 0.1.1): `ShipConfig.tag_type_id` + `tag_quantity` (migration 0002); `refresh_prices` includes tag types; `pricing.economics(tag_unit_price=…)` prices the tag at lowest sell ÷ runs and marks the ship incomplete while the tag price is missing; Blueprints & LP page shows the tag's current price; dashboard type filter = Bootstrap tick buttons, remembered in localStorage. Tests 21, all pass (run with an in-memory SQLite settings override: the `aauth` DB user cannot create `test_alliance_auth`).
- Deployed per section C: requirements SHA → build → check + tests + plan in a throwaway container → `migrate shipyard` → `up -d` (6 recreated) → nginx → collectstatic. Copy of the old requirements: `~/backups/requirements.txt.pre-0.1.1`.
- Data: LpFaction ISK/LP set (rows are named Imperial Navy / Caldari Navy / Federation Navy / Republic Fleet); the eight cruisers: lp_cost 18000, lp_isk_cost 0, lp_runs 1, tag_type_id per faction, tag_quantity 1, tag_cost_isk 0; `use_lp_pricing` on for `tony`. Dashboard check: all eight complete, blueprint from LP (16.2 M / 15.3 M / 12.6 M) plus tag (570,800 / 571,700 / 2,483,000 / 184,900 at the time).
- Then the remaining navy hulls, verified in ESI (militia stores, 1 run, no tag): 8 destroyers 12,000 LP + 3.5 M ISK, 8 battlecruisers 40,000 LP + 10 M ISK, 8 battleships 100,000 LP + 20 M ISK; all 24 complete on the dashboard. The four inactive special-edition battleships were touched by the hull filter and set back to "no offer". **Navy frigates have no LP offer yet** (the militia stores sell them too; ask the owner for the numbers or read them from ESI the same way: `/loyalty/stores/{corp}/offers/` for corps 1000179–1000182).
- **0.1.2 (commit `c9a9206`, deployed 14:45 UTC): blueprint policy by type.** `constants.BPC_POLICY`: Base → free (0 ISK), Navy → corp (LP-store cost incl. tag × 1 + `SHIPYARD_CORP_BPC_MARKUP`, default 5 %), Pirate/Trig/Edencom → public (blueprint and tag left out, `econ.bpc_excluded` True, dashboard and detail page show "public contracts only" and a `no BPC` marker next to net profit), ORE/Other → manual. `pricing.blueprint_cost(config, use_lp, category)`; `economics(category=…)`; the simulation passes `category=None` when a blueprint price is typed, so a typed quote wins. Two board tests were updated to the policy (the Vindicator fixture is a pirate hull). 22 tests pass.
- **0.1.3 / 0.1.4 (commit `3c84742`):** no `LP+5 %` marker, value only (owner: "just list the value"); Base hulls read "Free for corp members"; ORE/Other with a 0 typed price read "not priced yet". Owner asked to make sure the calculator uses the +5 % price: it does (dashboard and detail), the marked-up blueprint and tag are inside `total_cost`; only a price typed in the simulation bypasses the markup.
- **0.1.5 (commit `414f9b3`):** base battleships → public (`BPC_POLICY_BY_HULL`), the rest of Base stays free. `blueprint_cost(..., hull_size)` / `economics(hull_size=…)`.
- **0.1.6 (commit `6f2c491`):** hull "Hauler" → "Industrial" (`HULL_GROUPS[28]`), group 941 added as Industrial (Porpoise; Orca in `INACTIVE_BY_DEFAULT`; the unpublished ORE Development Edition is skipped by `classify`); hull filter is multi-select (shared `remember()` helper in dashboard.js, localStorage keys `shipyard.categories` / `shipyard.hulls`); `no BPC` marker on the simulation panel's first render. Deployed with `shipyard_load_ships --no-seed` + `shipyard_refresh` afterwards. 23 tests.
- **Preset stations (owner's request):** four public Piekura Raitarus (The Zero-Complaints Logistics Division, 2 % tax) created as `Facility` rows with the rig type IDs resolved from the in-game bios (ESI `universe/ids`): Big ship Construction [37152, 43733, 43871]; Fuel/Ammo/Equipment [37159, 43921, 43875]; Small Ships & Drones [43855, 37154, 37156]; Medium Ship & Comp. [43866, 43859, 37146]. System Piekura 30001391 (index 0.0526 vs Isikano 0.0375). `refresh_facility_indices` + `refresh_builds` ran: 875 build snapshots, all five facilities × 175 active ships.
- Section B for the owner now also covers: on Blueprints & LP, set a tag type ID for other LP-store ships if wanted; the filter buttons on the dashboard; the blueprint policy markers; picking one of the Piekura stations under My settings.

### Also today (local)
- Three members whose corp change had not reached auth were refreshed by hand (Lexxus, phoenix4, Josh Havenguard → OARMI/ORLOV, Family Member, Discord nickname and roles followed). Cause: EVE's public character record is cached 24 h while the affiliation endpoint refreshes hourly; auth's character update picks the new corp up as soon as it runs. Owner's command for this: "update user <name>" in a local session.

### Shipyard: sheet vs app check and 0.1.7 (laptop session, 2026-10-07 16:00–16:50 UTC)
- Owner's question: sheet v3.2 shows Vindicator 52.4 M profit with a 23 M blueprint, the app does not. Line by line (same quantities, Isikano Raitaru, Jita): sell 950 M both; materials 810.6 M (sheet) vs 814.0 M (app), same lowest-sell basis, different minute; job cost 18,239,547 identical; taxes 45.7 M (sheet, flat 4.81 %) vs 46.3 M (app, 3.375 % + 1.5 %); blueprint 23 M (sheet) vs **0** (app: Pirate → "public contracts only", `no BPC`). App shows 71.4 M; with 23 M typed in the simulation 48.4 M. So the gap is the blueprint policy, not arithmetic. **Open for the owner:** honour a typed blueprint price for "public" hulls (runbook 13 B tells the owner to enter the sheet's prices, but the code ignores them for pirate hulls). Recommended; not implemented yet.
- Owner asked for standings. Facts (EVE University wiki, Aug 2026): sales tax 7.5 % × (1 − 0.11 × Accounting), no standings effect; NPC broker fee 3 % − 0.3 pp × Broker Relations − 0.03 pp × faction standing − 0.02 pp × corp standing, unmodified standings. Catherine Frey: Caldari State −0.27, Caldari Navy +2.34 → 1.461 % instead of 1.5 %.
- **0.1.7 released** (commit `24725dc`, see runbook 13 C log): `MarketLocation.owner_corporation_id/owner_faction_id`, `UserSettings.standings` (+ `standings_fetched_at`), migration 0003 (sets Jita's owners), `esi.character_standings`, `load_skills` reads standings too (scope added), `pricing.tax_rates` applies them, settings page shows them, 25 tests. Server: backup `aa-db-2026-10-07-1638.sql.gz`, `requirements.txt.pre-0.1.7` in `~/backups`, build, checks in a throwaway container, migrate, `up -d`, nginx, collectstatic, site 200. The owner's standings (83 entries) were stored from the server through Catherine Frey's token; Vindicator fees now 45.94 M (sheet 45.70 M).
- Sheet location for later checks: `OneDrive/EVE/ships dashboard v3.2.xlsx` on the laptop (older versions in the owner's Google Drive). Read it with openpyxl from a copy; OneDrive refuses direct reads.
- **New request from the owner (not started):** a front-end outside auth at e.g. `shipyards.orlovfamily.space`: login via EVE SSO only, data pulled from ESI so it cannot be wrong, and the characters already on the member's auth account available there. Needs a design (hosting, domain, SSO app, link to auth's user) before any code; the laptop session is writing it up.

### Shipyard front door, phase 1 released with the door closed (laptop session, 17:05 UTC)
- Owner's decisions for `shipyards.orlovfamily.space`: Family Member **and** Family Friend; pull in **everything** (the 33 Member Audit scopes); existing server (headroom checked: 1.8 GB free, load 0.2, 68 GB disk). Plan: `docs/research/06-shipyards-frontend.md`; steps: `docs/runbooks/14-shipyards-front-door.md`.
- **Shipyard 0.2.0** (commit `7fe6752`): `shipyard/middleware.py` (host routing, SSO bounce `/shipyard/go/`, no-access page), `services/characters.py` (full scopes from Member Audit's `Character.esi_scopes()`, token lookup, Member Audit registration, daily ESI refresh), templates `frame_standalone.html` / `frame_auth.html` (base.html extends the `frame` context variable), new settings page with the character picker (`use_character` view: POST → SSO once if no full-scope token; `shipyard_sso_pending` session key), manual skills and tax overrides removed, `load_skills` gone. 37 tests (`tests/test_frontdoor.py`). Dry run before the release ran the working copy inside a throwaway container (`-v ~/shipyard-dev/apps/shipyard:/dev/shipyard`, `PYTHONPATH`), useful pattern.
- Server: released per runbook 13 C with **`SHIPYARD_STANDALONE_HOST = ""`** (door closed) plus `MIDDLEWARE +=`, `SESSION_COOKIE_DOMAIN`/`CSRF_COOKIE_DOMAIN = .orlovfamily.space`, `CSRF_TRUSTED_ORIGINS +=` (local.py now 238 lines; copies `local.py.pre-0.2.0`, `requirements.txt.pre-0.2.0`, backup `aa-db-2026-10-07-1701.sql.gz`). Permission `shipyard.basic_access` added to the states Family Member and Family Friend.
- **Open — owner (runbook 14 A):** DNS `A` record `shipyards` → 167.99.207.145 at Porkbun; proxy host with certificate in Nginx Proxy Manager. **Then local session (14 C):** set the host in `conf/local.py`, restart gunicorn + workers, verify the redirects. Then the owner checks (14 D).
- Still open from earlier: honour a typed blueprint price for "public" hulls (Vindicator 71 M vs sheet 52 M); front-door phase 2 (blueprints, jobs, assets in the dashboard).

### Shipyard 0.3.0: My industry (phase 2), laptop session, evening of 2026-10-07
- Owner: "phase 2, go for it: a full dashboard of the ongoing jobs and assets"; then: Family Members see only their own characters' slots, Corp Directors everything in their corp, Alliance Directors everything in the alliance.
- New: `services/industry.py` (sync per character: jobs 30 min / blueprints and assets 6 h, assets rolled up to the root location and kept only for known types, name caches `MaterialType`/`LocationName`, `owned_blueprints()`, `overview(user, scope)`, `allowed_scopes()`/`visible_syncs()`), models `CharacterSync`, `IndustryJob`, `CharacterBlueprint`, `CharacterAsset`, `LocationName` (migration 0004, **already applied to the live DB from the working copy during the dry run**), permissions `view_corp_industry` / `view_alliance_industry`, task `refresh_industry` + beat entry in `deploy/conf/local.py.append`, page `industry.html`, nav entry, dashboard badge and live ME/TE from own blueprints (`board.dashboard_rows`, `views.ship_detail`), ESI helpers (paged, authed). 47 tests.
- Dry run (working copy in a throwaway container, real ESI): tony's 10 characters in 8.8 s, 232 blueprints, stock 3.5 B at 29 places, 14 catalog ships with own ME 10, page 200 in all scopes, Tiptoe (no permission) sees no scope buttons and nobody else. Thorax and Stabber share one material list at every ME: EVE data, not a bug.
- **Released 17:50 UTC** (commit `07f5edb` pinned): backup `aa-db-2026-10-07-1744.sql.gz`, `requirements.txt.pre-0.3.0` and `local.py.pre-0.3.0` in `~/backups`, beat entry `shipyard_refresh_industry` appended (local.py 244 lines), build, throwaway checks (47 tests, no pending migration), `up -d`, nginx, collectstatic, site 200. Permissions granted: `view_corp_industry` → group Corp Director (3 members), `view_alliance_industry` → group Alliance Director (1). Live: tony's page 200 in all scopes; MrFreshy_Valterus (Corp Director) sees "My corp" but no "Alliance"; beat shows the new entry enabled; 0 errors.
- **Still closed:** the front door (`SHIPYARD_STANDALONE_HOST = ""`) until the owner does runbook 14 A (DNS + proxy host); then 14 C.

### Also 2026-10-07 (laptop session)
- "refresh user Francis01": FNA → OARMI/ORLOV, Family Friend → Family Member, `corp_OARMI`, Discord roles and nickname synced. Procedure written up as runbook 04 section E. Francis01 is not yet in Early Founders; the owner triggers that with "refresh the founders".
- 2026-10-06: Discord's join messages (System Messages Channel) moved from `#how-to-get-roles` to `#public-chat`; see the entry below.

### Owner does by hand (browser)
- Runbook 13 section B with the cloud session: My settings (facility rigs, market, load skills), Blueprints & LP prices, compare five ships with the sheet, try the simulation page.

### Next — cloud session
- Walk the owner through section B; collect any mismatch against the sheet and fix in the plugin (then a new pinned commit → runbook 13 section C via the local session).

---

## 2026-10-07 (12:30 UTC) — cloud session → local session

**Runbook:** `docs/runbooks/13-shipyard-plugin.md` — section A (install the Shipyard plugin, private test release).

### Done (cloud)
- Built the **Shipyard** Alliance Auth plugin in `apps/shipyard/` (dashboard, ship detail with simulation, per-member settings incl. ESI skills, Blueprints & LP manager page, Celery refresh, catalog loader). 19 unit tests pass; wheel builds with templates/static/migrations included. Plan: `docs/research/05-industry-dashboard.md`.
- `deploy/conf/requirements.txt` has the install line with a `<commit-sha>` placeholder; `deploy/conf/local.py.append` has the Shipyard block (INSTALLED_APPS + two beat entries).
- Nothing is released: no group has the permission; the superuser `tony` sees the menu automatically.

### Next — local session: runbook 13 section A
Announce every state change first, one at a time, show output. Steps:
1. Pull the branch; note the full SHA of HEAD (`git rev-parse HEAD`). Check the stack is up. Run `~/bin/aa-backup.sh`.
2. Append the Shipyard line to `~/aa-docker/conf/requirements.txt` with `<commit-sha>` replaced by that SHA (idempotent: skip if a line starting with `orlov-shipyard` exists; replace the SHA if it differs). Show the file.
3. Append the Shipyard block from `deploy/conf/local.py.append` (from `# --- Shipyard` to the end of the file) to `~/aa-docker/conf/local.py` unless `"shipyard"` is already in it. Show the tail. Never print .env.
4. `docker compose --env-file=.env build` (watch for a pip error on the orlov-shipyard line — if the archive download fails, report it and stop), `up -d`, `restart nginx`; confirm the site answers.
5. Via `docker compose exec -T allianceauth_gunicorn python /home/allianceauth/myauth/manage.py <cmd>`: `check`, `migrate shipyard`, `collectstatic --noinput`, `shipyard_load_ships`, `shipyard_refresh`. Report the counts each prints (expect ≈190 ships, four refresh steps ok).
6. Verify in Django: `Ship.objects.count()`, active count, `BuildSnapshot.objects.count()`, `PriceSnapshot.objects.count()`, `RefreshRun` rows with ok/message. Report anything not ok with the message.
7. Write the next handoff entry (what was done, SHA used, any error text), commit, push. Then the owner does runbook 13 section B in the browser with the cloud session.
Rules from CLAUDE.md apply (backup first, no rm -rf, nothing in mysql-data/, never print .env).

---

## 2026-10-06 (12:45 UTC) — local session (PC) → either session

**Not a runbook step.** Membership changes on the owner's instruction, plus a research document.

### Done (auth, via Django)
- **Go Browns [GB44]** (corp_id 98845722) was accepted into the alliance; ESI shows the alliance only after the 24 h join delay. One-off: GB44 added to the `Family Member` state's `member_corporations` (now OARMI, GWON, GB44). Auth moved **Masterxxx** and **MrFreshy_Valterus** (3 characters) from Family Friend to Family Member at once; Discord roles and `[GB44]` nicknames followed within a minute.
- Both users added to the **Corp Director** group (owner's instruction); the Discord role followed. Corp Director members are now tony, Masterxxx, MrFreshy_Valterus.
- **Open: remove GB44 from the state's corporations once ESI shows Go Browns in ORLOV** (admin → Authentication → States → Family Member, or via Django), so membership follows the alliance again. Noted in `docs/design/membership.md`.

### Also
- `docs/research/04-corp-industry-and-projects.md`: how corp blueprints, hangars, Corporation Projects and payouts work, with scenarios and theft risks; for the owner to consult.

---

## 2026-10-06 — local session (laptop) → either session

**Topic:** Discord's join messages moved from `#how-to-get-roles` to `#public-chat`.

### Done
- The "welcome" lines when somebody joins were **Discord's own system messages**, not the bot: the server's System Messages Channel was `#how-to-get-roles` (flags 0 = all system message types on). The bot has no welcome feature active (`DISCORD_BOT_COGS` = about, time; aadiscordbot WelcomeMessage/GoodbyeMessage tables empty).
- Changed the server setting to `#public-chat` through the Discord service's API client (`PATCH guilds/{id}` with `system_channel_id`), read back: system messages channel = public-chat. Reversible in Discord: Server Settings → Overview → System Messages Channel.
- No repo files other than this one changed. Previous session's open items (owner checks of `#jf-gank-board`, `#zkillboard`, the 3 Nov reinforcement date, Go Browns joining, profile names, Alliance Director read-only on the boards) are unchanged; see the 2026-10-05 15:15 entry.
