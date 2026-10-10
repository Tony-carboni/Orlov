# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-10 (13:50 UTC) — desktop session → any session

**Runbook / topic:** runbook 11 (kill feed): the owner asked why kill 139051327 (13:23 UTC, a 1.17 B kill with one alliance pilot on it, eleven more kills in the same fight by 13:26) was not in `#zkillboard`.

**Finding.** The bot is healthy (cog loaded, loop running, last posts 00:19 and 04:39 UTC today, no errors). zKillboard's API is cached by **Cloudflare for one hour** (`cache-control: public, max-age=3600`). The server's copy of `/api/allianceID/99015337/` was served at 13:19:39 (`cf-cache-status: HIT`, `age` 1315 at 13:41, `expires` 14:19:39) and holds 4 killmails; the owner's PC, on another edge, already saw 12. So the feed posts the fight at its first check after 14:19 UTC, 10 killmails then and the last 2 five minutes later. Verified by running the cog's `collect()` and `plan()` by hand from the gunicorn container (read-only): plan would post nothing until the cache turns. Runbook 11 corrected (the "within minutes" claim) and a troubleshooting entry added.

**Options for the owner (nothing changed yet):**
1. Live with up to an hour of delay (current behaviour, zero work).
2. Cache-bust: add a changing query string per 5-minute check (`?_=<bucket>`), which makes Cloudflare fetch fresh, at most 12 backend requests per hour per entity. Small code change in `deploy/orlovbot/cogs/killfeed.py`; zKillboard sets that cache on purpose, so this is slightly impolite but light.
3. Switch the feed to zKillboard's RedisQ (`https://zkillredisq.stream/listen.php?queueID=...`): near real time, the way zKillboard intends for live feeds; the bot long-polls every ~10 s and filters our alliance out of the global stream. A few hours of work and a new cog loop.

**Owner has to do by hand:** nothing. Decide between the options above.

### Next — any session
If the owner picks option 2 or 3: implement in `deploy/orlovbot/cogs/killfeed.py`, copy to `~/aa-docker/orlovbot/cogs/`, restart the bot container (announce first), check the log for `posted` lines, update runbook 11. Shipyard is at 0.9.6 (commit `5c804b6` pinned). Cartographers [1E3] fully prepared (see the 07:30 entry).

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
- When Eemar has authed: add them to the `Corp Director` group (auth admin) and send them `docs/guides/corp-ceo-onboarding.md` (Corp Stats / Member Audit token).
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

## 2026-10-09 (08:55 UTC) — desktop session → any session

**Runbook / topic:** runbook 13 C, Shipyard **0.8.5 to 0.8.7 released** (owner's requests of 2026-10-09: the Scrapmetal and Reprocessing tables easier to read).

**Done**
- Confirmed for the owner: Scrapmetal **Value** = Σ floor(quantity × yield) × Jita lowest sell × (1 − tax), yield from the character's Scrapmetal Processing (V for the owner), tax 0 at the Isikano Raitaru.
- **0.8.5** (commit `ce24e15`): Scrapmetal ISK columns in whole thousands (exact amount on hover); **Gives** column = each mineral's share of the value with its in-game icon, the three largest with a percentage, the rest dimmed icons, names still searchable; **column widths** draggable at the header's right edge, remembered per browser, double-click resets.
- **0.8.6** (commit `83525a8` pinned): the Reprocessing tab gets the same Gives column and size-based ISK rounding (two decimals under 10 k, one from 10 k, none from 100 k, millions keep two; filter `isk_auto`) for Value, Sell, Buy and the price points. Tests 68.
- **0.8.7** (commit `77b512c` pinned): a **Columns** button on both tables (tick boxes, remembered per browser), m³ hidden by default, Show all restores; backup `aa-db-2026-10-09-0847.sql.gz`; collectstatic was run from a throwaway container before `up -d` because of the new `columns.js` (lesson noted in runbook 13 C).
- All released per runbook 13 C (backups `aa-db-2026-10-09-0740.sql.gz` and `-0833.sql.gz`, `requirements.txt.pre-0.8.5/.pre-0.8.6` in `~/backups`, build, throwaway `check`, `up -d`, nginx, collectstatic, served CSS/JS verified, 0 gunicorn errors). No migrations.
- Fixed on the PC: the SSH key `~/.ssh/orlov-claude` had Windows line endings and no trailing newline (OpenSSH: "invalid format"); rewritten with LF and a final newline, read-only ACL restored, backup `orlov-claude.crlf-backup` beside it. Git identity set for this repository only. The first push needed a one-time GitHub sign-in in the Git Credential Manager window; the credential is stored now.
- Python 3.12.10 installed for the owner's user via winget (the owner asked); on the user PATH for new terminals.

**Open (owner)**
- Look at both tabs on `shipyards.orlovfamily.space`: icons in Gives, the rounding, drag a column edge on Scrapmetal, use the Columns button. Say if the percentages should cover more or fewer than three minerals, if the icons should be bigger, or if the Reprocessing tab should get draggable columns too.
- From earlier: Scrapmetal group names (say if any should change); more modules via admin → Shipyard → Scrap items or a list for the local session.

### Next — any session
Nothing queued. The Shipyard is at 0.8.7 on the server (commit `77b512c` pinned).

---
