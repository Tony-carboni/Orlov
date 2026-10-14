# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-14 (desktop session) — alliance news site, runbook 15

**Done (desktop).** Public page for State-of-the-Union style reports: `site/alliance/` in the repo (Markdown posts, `build.py`, dark template), served by a new `alliance_site` nginx container on the server (`~/aa-docker/alliance-site/`, service appended to `docker-compose.yml`, backup `docker-compose.yml.pre-alliance-site`; 12 containers up). First draft post built and copied; `curl http://alliance_site/` from the proxy container answers 200. Runbook 15 written.

**Also (11:10 UTC):** Shipyard 0.11.0, the **Structure income** tab (runbook 13 C): GWON wallet ledger, income per period and per payer, hourly task; migration 0016 applied, beat entry added, 79 tests, 12 containers up. **Owner:** on https://shipyards.orlovfamily.space/shipyard/income/ press *Connect the wallet* and log in to EVE with Vieze Jonge Pass (GWON's CEO), accept both scopes; then *Read the wallet now*. Done by the owner at 11:15; 0.11.1 fixed the payer corporations and the header badge; ledger 1,122 entries since 2026-09-14, 74 M income in the last 30 days (OARMI 40 M, Ceken 22 M, Max Caulfield 10 M).

**Also (11:30 UTC):** Shipyard 0.12.0, the **Corp projects** tab (runbook 13 C, research 08): OARMI projects snapshotted hourly, payouts per period, contributors; migration 0017, beat entry, 81 tests, 12 containers up. **Owner:** on https://shipyards.orlovfamily.space/shipyard/projects/ press *Connect the projects* and log in to EVE with Catherine Frey, accept the scope; then *Read the projects now*. 0.12.1 fixed the DataTables column-count warning on the empty projects page.

**Naming (owner, 2026-10-14):** the site at alliance.orlovfamily.space is called **the alliance website** from now on. The first post, "State of the Union, October 2026" (full version, written with the owner), is built and copied to the server; the owner writes the in-game mail summary himself and links to https://alliance.orlovfamily.space/2026-10-14-state-of-the-union-october-2026.html.

**Also:** Tavaga (Discord flambo2018) added to the auth group `FC` on 2026-10-14, Discord roles pushed (True).

**Discord (2026-10-14, through the auth bot's token):** `#pings` under Member channels is now read-only for Family Member (view, history, reactions; no posting, threads or mentions) and FC, Corp Director and Alliance Director may post and use @everyone/@here. A second, stray `#pings` outside any category exists; the owner deletes it by hand if unwanted.

**Owner does by hand:** runbook 15 A (Porkbun A record `alliance` to 167.99.207.145) and C (Nginx Proxy Manager proxy host `alliance.orlovfamily.space` to http://alliance_site:80 with a Let's Encrypt certificate). Then write the real post in `site/alliance/posts/` and say "publish the alliance news" to a local session (15 D).

**Also since the last entry:** Republic Fleet LP value 725 ISK/LP (2026-10-13); Shipyard 0.10.3 (Blueprint column includes the cruiser tag); guide `docs/guides/corp-roles.md`.

---

## 2026-10-14 (07:30 UTC) — desktop session → any session

**Runbook / topic:** alliance roster coverage, **runbook 15** (corp roster token for CEOs and directors) and **Shipyard 0.10.4** (every scope at the front door), on the owner's request.

**Findings.** EVE: 43 characters in 3 corps (OARMI 30 → 31 during the day, GB44 11, 1E3 2). Auth: 38 registered on 22 accounts, all Family Member. Missing by name (read through Catherine Frey's and Masterxxx's membership-scope tokens): OARMI Goedweer2, Goedweer3, Goedweer4, Goedweer5 (alts of Goedweer1, surely) and Miguel Stevens; GB44 complete; 1E3 one of two, unnamed because Eemar's token has only the basic scope. Hamu (asked about on 2026-10-11) is user `Hamu`, character Hamu 978861931, CAS at the time, OARMI since; Family Friend then, Family Member now; Discord roles were already right.

**Done**
- Permissions: `Corp Director` += corputils *add_corpstats*, *view_corp_corpstats*; `Alliance Director` += those and *view_alliance_corpstats*. Nobody but the superuser had them, so the old CEO guide's "any member can add the Corp Stats token" was wrong in practice.
- `docs/runbooks/15-corp-roster-token.md`: for CEOs/directors, browser only (add page `/corpstats/add/`, one scope, where the lists show, Update button, troubleshooting) and the executor's section (Corp Director group). CEO onboarding guide points to it; CLAUDE.md lists it; membership design change log updated.
- Corp Stats exists for OARMI only (token Catherine Frey, refreshed hourly at :00).
- **Shipyard 0.10.4 released** (commit `184182b` pinned, backup `aa-db-2026-10-14-0945.sql.gz`): owner's rule "scopes as wide as can be": the front door now asks a character for every scope EVE offers (73 = Member Audit's 33 + ESI's 72 + publicData, write scopes included; `SHIPYARD_REQUEST_ALL_SCOPES`, `SHIPYARD_EXTRA_SCOPES`). Tokens are still looked up with the 33, so nobody has to log in again now; the wider set comes with the next login. Member Audit's own Add-character button still asks for its 33 and cannot be widened. Runbook 15 therefore starts with "register the character at the front door"; runbook 14 known values and the member guide (shortcut) updated. Tests 77. Details in runbook 13 C.

**Owner has to do by hand**
- Send Eemar (and Masterxxx for GB44 if you want their roster in auth too) **`docs/guides/corp-ceo-roster-token.md`**, the CEO-facing version via the auth portal (Member Audit registration, 33 scopes, then the Corp Stats add page reuses the token); Eemar is in `Corp Director` already. Note: through auth a character gets Member Audit's 33 scopes, the 73-scope login exists only at the Shipyard front door (Member Audit's button cannot be widened); an auth-side "register with every scope" page is possible if the owner wants the wide set through auth too.
- Nudge Goedweer1 to add Goedweer2–5 to their account, and Miguel Stevens to auth.

### Next — any session
Nothing queued. Shipyard 0.10.4 (commit `184182b` pinned), kill feed with live R2Z2 feed, structure board without fuel pings (2026-10-11).

---

## 2026-10-11 (06:05 UTC) — desktop session → any session

**Runbook / topic:** runbooks 09 and 10: the moon board showed no extraction and the structure board showed Orlov Mining Facility II as ABANDONED while, in game, it was online, fuelled and extracting. Plus the owner's rule: **no more fuel pings**.

**Finding.** Nothing was broken. EVE's own API was behind: queried directly with the GWON owner token at 05:30 it still returned zero extractions (answer dated 05:10, cached until 05:40) and Facility II as "onlining, no services, no fuel" (dated 04:50, cached until 05:50). Auth's notifications show the real timeline: online 2026-10-10 19:17, fuelled (high power) and extraction started 05:23/05:24 on 2026-10-11, extraction on Facility I started 05:28. With no fuel and no online record the Structures app files a structure under power mode "Abandoned?", which the board prints as ABANDONED. Once the caches turned, the 05:50 Moon Mining run and the 05:51 forced refresh of both apps picked everything up: two refineries (Piekura I, Saatuban II), extractions arriving Sat 17 Oct 15:01 (II) and Fri 23 Oct 17:01 (I), Facility II shield vulnerable, full power, fuel to 2027-01-11, Moon Drilling online. Moon board updated 05:50, structure board 05:56 (after the restart below). Rendered from the bot container to confirm both rows. Runbook 10 troubleshooting has the interpretation (owner: once-only per structure, no UI change).

**Done.** Fuel pings removed on the owner's instruction: `FUEL_PINGS = False` in `deploy/orlovbot/cogs/structures.py` (`structure_problems()` skips the fuel kind; services pings, war messages and the one "Anchoring finished" message stay; the anchoring message no longer carries a fuel line). Backup `~/backups/structures.py.pre-no-fuel-pings`, file copied, bot restarted 05:56 UTC, all four cogs loaded, boards found. Runbook 10 (alert table, changing things, anchoring row) updated.

**Also (desktop, 2026-10-11):** "refresh user Ranos Zain" done per runbook 04 E: character record FNA → OARMI/ORLOV, state Family Member and `corp_OARMI` were already right, Discord roles and nickname pushed (both True).

**Also (desktop, 2026-10-12):** Sabbard added to the auth group `FC` (Discord role pushed, True). Braadslee added to `FC` the same way (2026-10-12 evening, Discord role pushed, True). 2026-10-13: Republic Fleet LP value set to 750 ISK/LP (was 700) on the owner's instruction; all Minmatar fleet issue blueprint costs follow (e.g. Typhoon Fleet Issue 95 M, Hurricane Fleet Issue 40 M, Stabber Fleet Issue 13.5 M before markup). Then 0.10.3 (commit `99b7714`): the Blueprint column includes the cruiser tag (Stabber Fleet Issue 13.68 M all in). Later on 2026-10-13 the owner sealed a large LP batch: Republic Fleet set to 725 ISK/LP (Typhoon/Tempest Fleet Issue 92.5 M, Hurricane/Cyclone 39 M, Stabber/Scythe 13.23 M all in, before markup). Guide written: docs/guides/corp-roles.md (every corporation role and what it allows; Communications Officer = bulletins, MOTD, calendar, corp bookmarks). Research doc 08 written: ESI has corporation project routes (scope `esi-corporations.read_projects.v1`, compatibility-date header required); a weekly/monthly report is buildable, nobody holds the scope yet; owner to decide shape and channel.

**Also (desktop, 2026-10-12 19:10 UTC):** Shipyard 0.9.7 released: new permission `reprocessing_access` = the Reprocessing tab only through the front door; granted to Hamu (he sees nothing else, lands on /shipyard/reprocessing/). Then 0.10.0: members set their own reprocessing skills and implant on the Reprocessing tab (card "Your skills", by hand or from EVE; default stays V + RX-804). Then 0.10.1/0.10.2: the Reprocessing tab requires a chosen character (skills from EVE, implant by hand) and access is per tab: Hamu holds `reprocessing_access` + `dashboard_access` (Dashboard, ship pages, My settings, Reprocessing; nothing else). Server pinned at `8ac5d89`, migrations through 0015, 76 tests.

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

