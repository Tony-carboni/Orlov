# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

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


---

## 2026-10-05 (15:15 UTC) — local session (laptop) → either session

**Topics:** structure board war banner (see below), and joining corp **Go Browns [GB44]** prepared in the role system before any of its members authed. **Corrected by the owner at 15:45 UTC: GB44 is not yet in the alliance, so its members are Family Friend until it is.** Design doc `docs/design/membership.md` updated.

### Done on the server (via Django, Alliance Auth's own functions)
- Corp looked up on public ESI: Go Browns, ticker GB44, corporation_id 98845722, 11 members, founded 2026-10-03, **no alliance**, CEO Masterxxx (character_id 2122385466).
- `EveCorporationInfo` created (pk 9). It was first added to the `Family Member` state's member corporations and **removed again at 15:45 UTC on the owner's instruction**: nobody gets Family Member before their corp is actually in The Orlov Family in game. The state is back to alliance ORLOV plus corps OARMI and GWON. No GB44 account existed on auth in between. Rule recorded in `docs/design/membership.md`: a joining corp is not listed on the state.
- Auto-group `corp_GB44` created in advance with `AutogroupsConfig.create_corp_group()` (group pk 10, managed link to config pk 3, 0 members).
- Discord role `corp_GB44` created in advance with the Discord service's `match_or_create_role_from_name()` (role id 1556685567536930900, no colour, no permissions, at the bottom of the role list).

### What happens when a Go Browns member auths
- While GB44 is outside the alliance: state Family Friend → Discord roles `Family Friend` + `corp_GB44` (the corp auto-groups cover both states), nickname `[GB44] Name`.
- Once GB44 is in alliance ORLOV in game: Family Member follows by itself at auth's next character update, because the state is keyed on the alliance. Nothing to configure.

### Structure board: war banner (owner's request, deployed 15:14 UTC)
- War eligibility removed from the board (and the public ESI read for it). New first line in heading size: green circle + "NOT AT WAR", or red circle + "AT WAR" while any registered corp has a declared or running war. The war detail lines and the red colour bar are unchanged; the "Wars: none declared or running" line is gone.
- `deploy/orlovbot/cogs/structures.py` → server `~/aa-docker/orlovbot/cogs/structures.py` (old copy: `~/backups/structures.py.pre-war-banner`). Dry run in a fresh process first (live data green, synthetic war red, no alerts planned), then only the bot restarted. Bot output: "Structure status: board updated in #structure-board".
- Not yet confirmed by the owner: that Discord draws the banner as a big heading. If it shows as a plain line starting with `#`, change `BANNER_PEACE` / `BANNER_WAR` to a bold line.

### Early Founders badge (owner's request, 15:25 UTC; first named Founder, renamed 15:35 UTC)
- Auth group `Early Founders` (pk 11, internal, no permissions) and Discord role `Early Founders` (id 1556687406663598113, no colour, no permissions). Created as `Founder`, then renamed on the owner's request: the Discord role in place through the Discord service's API client (same id), then the group. Auth's own rate limiter stops a burst of Discord calls; pause between them.
- Rule decided by the owner (the literal request "joined before 2026" matched nobody: alliance founded 2026-10-01): **every Family Member account before 2027-01-01**; Go Browns members count once they are Family Member. Written into `docs/design/membership.md`.
- Added: tony, Flapoor_Hendrik (main Gewoon Rudi), Nashomon_Yoma_Itinen, Tavaga. All four verified to have the role in Discord.
- Not automatic. When the owner says "refresh the founders": add every account with state Family Member to the group (add-only), as long as the date is before 2027-01-01. Go Browns members need this once their corp is in the alliance and they show as Family Member.

### Kill feed (runbook 11, owner's request, live 15:39 UTC)
- New bot module `orlovbot/cogs/killfeed.py`: every 5 minutes it reads `zkillboard.com/api/allianceID/99015337/` and posts unseen killmails (not older than 3 days) in `#zkillboard` (category `bots`, created by the owner): green kill, red loss, max 10 per check, no pings. Seen ids live in the Django cache under `orlovbot:killfeed:seen`; a test post is queued with the cache key `orlovbot:killfeed:test`.
- Server: `orlovbot/` updated (old folder: `~/backups/orlovbot.pre-killfeed`), `conf/local.py` + "Kill feed" block (210 lines; copy from before: `~/backups/local.py.pre-killfeed`). Dry run clean (11 logic checks pass), only the bot restarted. Bot output: module loaded, "first run, 2 existing killmails count as already posted", "posted test (Loss: Capsule (Nashomon Yoma Itinen))".
- Slip to know about: the backup command contained an `rm -rf` on a path in `~/backups` that did not exist. Nothing was deleted, but it breaks the CLAUDE.md rule; do not repeat.

### Boards: "Last checked" (owner's request, same deployment)
- `orlovbot/board.py`: every board now ends with an entry "Last checked" (`<t:…:R>` and `<t:…:t>`), and the bot edits the board at every 10-minute check instead of only on change. "board updated" is still logged only when the content changed. Runbooks 09 and 10 updated.

### Board tidy-up after the owner looked (15:41–15:43 UTC, three bot restarts)
- Owner confirmed the war banner renders as a big heading with the green circle.
- Structure board: the "Structure data read from EVE" line is gone (the owner saw two times). It now appears only as a warning when the data is more than 90 minutes old (`DATA_STALE_AFTER` in `structures.py`), which also turns the colour bar orange.
- Both boards: footer "Kept up to date automatically, checked every 10 minutes" removed (`board.py`).
- Moon board and `/moons`: the "Your time" line was removed at 15:43 and **restored at 15:46 UTC as "In your time zone"** (`moons.py`). The owner had read it as the current time; it is the chunk's arrival time in the reader's device time zone (17:01 EVE time = 7:01 PM at UTC+2), and the owner wants it kept.
- Old copies in `~/backups`: `structures.py.pre-single-timestamp`, `board.py.pre-no-footer`, `moons.py.pre-no-local-time`.

### Structure board: colours, bigger titles, "War over" ping (owner's requests, live 15:51 UTC)
- Layout: each structure is now a `###` heading plus an `ansi` code block in the embed description (no embed fields any more). Colours: green normal state / full power / all services online; orange low power, services offline, fuel under 14 days; red abnormal state, abandoned, fuel under 7 days or none; fuel blue otherwise. The colour bar follows the worst line. The fuel hover link is gone (no links in code blocks); the run-out date is shown in grey.
- Alerts: new `@everyone` "War over" ping when a known war is no longer declared or running. It replaces the "War declared" message and is removed after 24 h (`WAR_OVER_KEEP`). No false ping when the corp merely drops off the board. The daily fuel ping still starts at 7 days.
- Dry run before the restart: live and synthetic layouts built, 12 alert scenarios pass. Bot output after restart: "Structure status: board updated in #structure-board", 0 errors. Old code: `~/backups/structures.py.pre-colours`.
- Not yet confirmed by the owner: how the coloured panels look, on desktop and on a phone (older phone apps may show the colours differently). Fallback if disliked: restore the backup file and restart the bot.

### Structure board: reinforcement hour (owner's request, live 15:57 UTC)
- New line "Reinforce: HH:00 EVE" per structure, from aa-structures (`reinforce_hour`, `next_reinforce_hour`, `next_reinforce_apply`). Green when it equals `ORLOVBOT_STRUCTURE_REINFORCE_HOUR = 21` (new setting, appended to `conf/local.py`, now 214 lines; the contract with the mercenaries on retainer requires 21:00), and also green when 21 is set but not yet effective (owner, 16:00 UTC: the in-game delay cannot be beaten), shown as "21:00 EVE (from 03 Nov, now 04:00)". Red for any other hour and when a change away from 21 is scheduled. No ping for it.
- Today both structures are green-pending: Orlov Family Facilities is at 04:00, Orlov Mining Facility I at 18:00, each with a change to 21:00 that EVE's data dates at 2026-11-03 18:35 UTC.
- Notes in brackets are no longer grey (unreadable on the dark theme); they use the normal text colour. Discord's ansi palette has no lighter grey.
- Old copies: `~/backups/structures.py.pre-reinforce-hour`, `~/backups/local.py.pre-reinforce-hour`, `~/backups/structures.py.pre-pending-green`.

### Jump freighter watch (runbook 12, owner's request, live 16:03 UTC)
- New module `orlovbot/cogs/jfwatch.py`: every 5 minutes one request to `zkillboard.com/api/losses/groupID/902/` (newest 200 JF losses, about two months). Highsec and lowsec only (zKillboard's `loc:` label; setting `ORLOVBOT_JFWATCH_SPACE`). A post per new loss (not older than 3 days) in `#jf-gank-board`, and a summary board "Jump freighter losses" kept as the last message: 24 h, 7 days vs the 7 before, 30 days, per-day bars, by hull, systems, final blows. `board.py` gained `drop()` (delete the board so it is re-posted at the bottom). Seen ids: cache key `orlovbot:jfwatch:seen`; test post: `orlovbot:jfwatch:test`.
- Server: files installed (old folder: `~/backups/orlovbot.pre-jfwatch`), `conf/local.py` + "Jump freighter watch" block (218 lines; copy from before: `~/backups/local.py.pre-jfwatch`). Dry run clean; bot output: module loaded, "first run, 10 recent losses count as already posted", "posted test (Rhea lost in Oinasiken (lowsec))", "board posted in #jf-gank-board", 0 errors.
- Same deployment: the structure board's fuel line no longer shows the run-out date in brackets (owner: just the days in colour).
- The owner moved `#jf-gank-board` and `#structure-board` to a category "leadership bots"; the bot finds channels by name, so nothing changes for it.

### Open (owner)
- Look at `#zkillboard` (test post), `#moon-board` and `#structure-board` ("Last checked" entry) and confirm they look right.
- Optional, in Discord: give the `Early Founders` role a colour or icon, and drag it where it should sit in the role list (it is at the bottom).
- When the CEO (Masterxxx) has authed: add them to the `Corp Director` group, and have them add the Corp Stats token (`docs/guides/corp-ceo-onboarding.md`).
- Tell a session when Go Browns has joined the alliance in game, so it can check the members switched to Family Member and refresh the founders.
