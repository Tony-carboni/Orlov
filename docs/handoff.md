# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-11 (06:05 UTC) — desktop session → any session

**Runbook / topic:** runbooks 09 and 10: the moon board showed no extraction and the structure board showed Orlov Mining Facility II as ABANDONED while, in game, it was online, fuelled and extracting. Plus the owner's rule: **no more fuel pings**.

**Finding.** Nothing was broken. EVE's own API was behind: queried directly with the GWON owner token at 05:30 it still returned zero extractions (answer dated 05:10, cached until 05:40) and Facility II as "onlining, no services, no fuel" (dated 04:50, cached until 05:50). Auth's notifications show the real timeline: online 2026-10-10 19:17, fuelled (high power) and extraction started 05:23/05:24 on 2026-10-11, extraction on Facility I started 05:28. With no fuel and no online record the Structures app files a structure under power mode "Abandoned?", which the board prints as ABANDONED. Once the caches turned, the 05:50 Moon Mining run and the 05:51 forced refresh of both apps picked everything up: two refineries (Piekura I, Saatuban II), extractions arriving Sat 17 Oct 15:01 (II) and Fri 23 Oct 17:01 (I), Facility II shield vulnerable, full power, fuel to 2027-01-11, Moon Drilling online. Moon board updated 05:50, structure board 05:56 (after the restart below). Rendered from the bot container to confirm both rows. Runbook 10 troubleshooting has the interpretation (owner: once-only per structure, no UI change).

**Done.** Fuel pings removed on the owner's instruction: `FUEL_PINGS = False` in `deploy/orlovbot/cogs/structures.py` (`structure_problems()` skips the fuel kind; services pings, war messages and the one "Anchoring finished" message stay; the anchoring message no longer carries a fuel line). Backup `~/backups/structures.py.pre-no-fuel-pings`, file copied, bot restarted 05:56 UTC, all four cogs loaded, boards found. Runbook 10 (alert table, changing things, anchoring row) updated.

**Also (desktop, 2026-10-11):** "refresh user Ranos Zain" done per runbook 04 E: character record FNA → OARMI/ORLOV, state Family Member and `corp_OARMI` were already right, Discord roles and nickname pushed (both True).

**Also (desktop, 2026-10-12):** Sabbard added to the auth group `FC` (Discord role pushed, True). Research doc 08 written: ESI has corporation project routes (scope `esi-corporations.read_projects.v1`, compatibility-date header required); a weekly/monthly report is buildable, nobody holds the scope yet; owner to decide shape and channel.

**Also (desktop, 2026-10-12 19:10 UTC):** Shipyard 0.9.7 released: new permission `reprocessing_access` = the Reprocessing tab only through the front door; granted to Hamu (he sees nothing else, lands on /shipyard/reprocessing/). Then 0.10.0: members set their own reprocessing skills and implant on the Reprocessing tab (card "Your skills", by hand or from EVE; default stays V + RX-804). Server pinned at `db939b6`, migrations through 0014, 76 tests.

**Owner has to do by hand:** nothing.

### Next — any session
Nothing queued. Shipyard is at 0.9.6 (commit `5c804b6` pinned). Kill feed with live R2Z2 feed since 2026-10-10. Cartographers [1E3] prepared, Eemar is Corp Director (token still to add by Eemar).

---

## 2026-10-10 (14:00 UTC) — desktop session → any session

**Runbook / topic:** runbook 11 (kill feed): **live feed from zKillboard's R2Z2 added** (owner's "go" on the real-time option after kill 139051327 and eleven more from a 13:23 fight did not show).

**Why.** zKillboard's API list (`/api/allianceID/…`) is cached by Cloudflare for one hour (`max-age=3600`); the server's copy was from 13:19, so the 5-minute check could not see the fight before 14:19. The bot itself was healthy.

**What was done**
- RedisQ was the plan, but it was sunset on 2026-05-31 (archived repo) and `zkillredisq.stream` resolves to 127.0.0.1 everywhere. zKillboard's replacement is **R2Z2**: every killmail as `https://r2z2.zkillboard.com/ephemeral/<sequence>.json` (fields `killmail_id`, `hash`, `esi`, `zkb`, `uploaded_at`, `sequence_id`), pointer `sequence.json`, rules: 6 s wait after a 404, at most 15 requests/s, a User-Agent. The third-party relay `killmail.stream` also works (RedisQ-compatible, packages without the killmail body) but was not used.
- `deploy/orlovbot/cogs/killfeed.py` (commit `e68e472`): second loop `stream` in the cog reads the files from the remembered position (cache key `orlovbot:killfeed:sequence`, started at the pointer), up to 50 per round at 0.1 s, 6 s pause on 404, `involves_us()` keeps killmails with our pilots on either side, `plan_stream()` applies the same 3-day window and the same seen-memory as the 5-minute check (which stays as fallback), `prepare_stream()` remembers then posts. Backlog over 3000 files after an outage → skip to the pointer with a warning. Failures: one warning, then one per 15 min, 60 s backoff. HTTP runs in a non-thread-sensitive thread so the long rounds never block the other cogs' database thread. Setting `ORLOVBOT_KILLFEED_STREAM` (default True; documented in `deploy/conf/local.py.append`, not added to the server's `local.py`, the default applies).
- Dry run in a throwaway container: pointer, file, 404, a round of 14 files in 2.1 s, filter and memory rules on the known kill, embed. Deployed 13:50 UTC: old cog in `~/backups/killfeed.py.pre-r2z2`, file copied, bot restarted; log `live feed starts at sequence 99956887`; the position then kept within a few files of the pointer, no errors.
- Runbook 11 rewritten where it matters (how it works, known values, changing things, troubleshooting, considered-and-not-used).

**Owner has to do by hand:** nothing. The 8 kills of ours from the 13:23 fight (Mastodon, Capsule, 6 Kikimoras, all by Simon Aurio; the other 4 killmails in the alliance list were older or already posted) were posted at 14:03–14:04 UTC after the live feed's position was set back by hand to sequence 99956250 (just before the fight); the memory of posted kills kept the fallback from repeating them at 14:19. Anything new arrives within seconds through the live feed. Rewinding = `cache.set("orlovbot:killfeed:sequence", <sequence>, None)` from the gunicorn container; files stay on zKillboard for 24 h.

### Next — any session
Nothing queued. If the live feed misbehaves: `ORLOVBOT_KILLFEED_STREAM = False` in `conf/local.py` and restart the bot, or put back `~/backups/killfeed.py.pre-r2z2`. Shipyard is at 0.9.6 (commit `5c804b6` pinned). Cartographers [1E3] fully prepared (07:30 entry).

---


## 2026-10-10 (07:30 UTC) — desktop session → any session

**Runbook / topic:** new joining corp **Cartographers [1E3]** prepared in the role system (owner's request from the in-game corp window); design doc `docs/design/membership.md` updated. Also: the owner's Naga job cost confirmed (3,930,942 ISK = system cost 1.90 M + facility tax 50.9 k + SCC surcharge 2.04 M = 7.72 % of the 50.93 M EIV; the dashboard uses EVE Ref's total, SCC included).

**Done**
- Corp looked up on public ESI: Cartographers, ticker 1E3, corporation_id 98846240, founded 2026-10-09 17:55, 2 members, **no alliance**, CEO Eemar (character_id 2116146613).
- `EveCorporationInfo` created (pk 14). **Not** added to the `Family Member` state (owner's rule of 2026-10-05: no Family Member before the corp is in the alliance in game); its members are `Family Friend` until then, and `Family Member` automatically once ESI shows the corp in ORLOV.
- Auto-group `corp_1E3` created in advance with `AutogroupsConfig.create_corp_group()` (group pk 14, managed link pk 10, hidden/internal, 0 members).
- Discord role `corp_1E3` (1558471529639976965) created in advance with `create_bot_client().match_or_create_role_from_name()` (`DiscordUser.objects.group_to_role()` returned nothing and created nothing in this AA version). The desktop session's auto-mode classifier had blocked the Discord write; the owner then added `~/.claude/settings.json` on the PC with an allow rule for `Bash(ssh orlov *)` and `Bash(scp * orlov:*)` (user scope, this PC only; the laptop already had the permission). The classifier also refuses to let a session write its own permission rules, so that file is the owner's to maintain.

**Owner has to do by hand**
- Nothing for the Discord role; it exists.
- Eemar has authed and is in `Corp Director` (done 15:16 UTC, Discord role synced). Still to send them: `docs/guides/corp-ceo-onboarding.md` (Corp Stats / Member Audit token).
- When the corp is accepted into the alliance: nothing; the state follows the alliance rule once ESI shows it (24 h join delay). Do not list 1E3 on the state.

### Next — any session
Nothing queued. Shipyard is at 0.9.6 on the server (commit `5c804b6` pinned, released by the other desktop session). Open for the owner from earlier entries: the ore-area table and the Scrapmetal group names.

---

## 2026-10-09 (14:30 UTC) — desktop session → any session

**Also (desktop, after the laptop's 0.9.4/0.9.5):** 0.9.6 released, millions show three decimals (2.850 M) in `isk_auto`, Scrapmetal price columns use it; server pinned at `5c804b6`. Structure board (runbook 10): no fuel pings while a structure anchors, one "Anchoring finished" ping afterwards; deployed to the bot 19:44 UTC, the alert for the anchoring structure 1055997584926 was cleared and its anchoring is tracked (timer ends 2026-10-10 19:16 EVE).
**Runbook / topic:** runbook 13 C, Shipyard **0.9.4 and 0.9.5 released** (owner's reports: sorting on the ship dashboard, then "sort by %" on the ore table).

**Done**
- **0.9.4** (commit `397acdf`): the column-resize handle (0.8.9, `columns.js`) on every header's right edge sits next to the sort arrows; a click landing on it was swallowed and silently froze all column widths. A resize now starts only after a 3 px move; a plain click sorts. Cross-checked on Dashboard, Fuel, Reprocessing and Scrapmetal.
- **0.9.5** (commit `e4e3477` pinned): the real cause of "sort by % doesn't work": the owner's browser asks for a decimal-comma language and his auth profile has no language set, so Django localised the raw floats in the `data-order` sort keys (`0,478`) and DataTables could not sort the %, price point and ISK columns. Number localisation is now off for every Shipyard page (`{% localize off %}` in `base.html`). Verified with Dutch and German `Accept-Language` on every tab: 0 comma keys. Tests 72.
- Both released per runbook 13 C (backups `aa-db-2026-10-09-1351` and `-1421`, `requirements.txt.pre-0.9.4/.pre-0.9.5` in `~/backups`, build, throwaway `check`, `up -d`, nginx, collectstatic, live verification, 0 gunicorn errors). No migrations.
- Members who hit the 0.9.4 bug may have frozen widths saved in their browser: double-click any header edge to reset.

**Owner has to do by hand:** nothing. Check: sort the ore table by Buy % and by a price point.

### Next — any session
Nothing queued. The Shipyard is at 0.9.5 on the server (commit `e4e3477` pinned). Open for the owner from earlier entries: the ore-area table and the Scrapmetal group names.

---


## 2026-10-09 (13:30 UTC) — desktop session → laptop session (owner continues there)

**State of play.** Shipyard is at **0.9.3** on the server (commit `0d5d678` pinned, 72 tests, 11 containers up, migrations applied through 0012, backups `aa-db-2026-10-09-1159` and `-1207`). Access is still the owner only (`shipyard.basic_access` on user `tony`). Everything below is in runbook 13 C; this entry is the map.

**Done today (desktop), newest first**
- 0.9.3 base hulls and fuel blocks priced at the corp's researched **ME 10 / TE 20** (`constants.RESEARCHED_ME_TE`, `Ship.default_me_te`; `refresh_builds` stores snapshots at the ship's default ME; 475 ME 10 snapshots computed by hand; ME 0 rows for base hulls remain in the table unused).
- 0.9.2 **All / None** on the ore-type lines and the scrap-group panel; **saved filter presets** (Presets dropdown) on Dashboard, Reprocessing and Scrapmetal (`shipyardSelectAll`, `shipyardFilterPresets` in `columns.js`, per browser).
- 0.9.1 **nearby buy orders**: `services/nearbuy.py` reads ESI regional buy orders per ore and scrap item inside the hourly `refresh_prices`, stores the highest order that reaches Jita 4-4 in `PriceSnapshot.buy_max_near` (station, anywhere in Jita above "station" range, Perimeter with range ≥ 1 jump, region-wide); the reprocessing and scrapmetal tabs use it for Buy and Buy %. 254 types, 93 had a better order outside the station on the first run.
- 0.9.0 **Fuel blocks tab** (`/shipyard/fuel/`, category `Fuel`, group 1136, `Ship.units_per_run` 40, figures per run; ship dashboard excludes Fuel; `catalog.iter_fuel()`; blueprint cell "own BPO").
- 0.8.9 draggable column widths on all three tables (shared helper); 0.8.8 Refresh button on every tab (returns to the same tab) and the Value column next to Buy % on the reprocessing table; 0.8.4 Metal scraps group; 0.8.3 Scrapmetal without Sell %.
- Checked for the owner: Hurricane profit sheet 7.92 M vs app 9.67 M = mineral and hull prices moving between 7 Oct and today; the sheet's 4.81 % is sales tax plus broker fee combined and the app's 3.37 % + 1.46 % matches it. No change needed.

**Owner does by hand:** nothing pending. Open for the owner when he gets to it: correct the ore-area table if any family sits in the wrong area (`DEFAULT_AREAS` in `services/reprocessing.py`, overrides via `SHIPYARD_ORE_AREAS` in `conf/local.py`); the Scrapmetal group names from the 08:55 entry.

**Next — laptop session.** No open step from this session; continue with the owner's next request. Procedure reminders: release per runbook 13 C (pin sha → build → check → migrate --plan → tests via the stdin script with SQLite → migrate → up -d → restart nginx → collectstatic → verify → docs); backup before any migration; tests count 72; the catalog of fuel blocks is loaded by `shipyard_load_ships` (now includes `iter_fuel()`), the ME 10 snapshots by the hourly/6-hourly `refresh_builds`. Patch scripts in the desktop's scratchpad are not in the repo; everything that matters is in the code and runbook 13.

---
