# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

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
- New line "Reinforce: HH:00 EVE" per structure, from aa-structures (`reinforce_hour`, `next_reinforce_hour`, `next_reinforce_apply`). Green when it equals `ORLOVBOT_STRUCTURE_REINFORCE_HOUR = 21` (new setting, appended to `conf/local.py`, now 214 lines; the contract with the mercenaries on retainer requires 21:00), red otherwise, and red when a change away from 21 is scheduled. No ping for it.
- **Both structures are red today:** Orlov Family Facilities is at 04:00, Orlov Mining Facility I at 18:00, each with a change to 21:00 that EVE's data dates at 2026-11-03 18:35 UTC. The colour bar stays green for this case (change to the agreed hour already scheduled).
- Old copies: `~/backups/structures.py.pre-reinforce-hour`, `~/backups/local.py.pre-reinforce-hour`.

### Open (owner)
- Look at `#zkillboard` (test post), `#moon-board` and `#structure-board` ("Last checked" entry) and confirm they look right.
- Optional, in Discord: give the `Early Founders` role a colour or icon, and drag it where it should sit in the role list (it is at the bottom).
- When the CEO (Masterxxx) has authed: add them to the `Corp Director` group, and have them add the Corp Stats token (`docs/guides/corp-ceo-onboarding.md`).
- Tell a session when Go Browns has joined the alliance in game, so it can check the members switched to Family Member and refresh the founders.

---

## 2026-10-05 (later) — local session (PC) → either session

**Runbooks:** `07-day-five-moon-timers.md` is **complete**. `08-day-six-moons-command.md`: A, B and C done; **D (owner tries `/moons` in Discord) is open.** `09-moon-board.md`: A and B done, the bot reported "Moon board posted in #moon-board" at 11:30 UTC; **C (owner confirms the message looks right) is open.** `10-structure-board.md`: A and B done, board posted 11:40 UTC; **C (owner confirms) and D (profile names) are open.**

### Changed since the previous entry
- **The Athanor moved corp.** The owner transferred it from KHAAS to **"Gewoon voor structures" [GWON]**, corp_id 98635713, 1 member, no alliance. The token character is **Vieze Jonge Pass** (sole member, so CEO; on the `tony` account), not Flapoor Hendrik. Wherever older entries say Flapoor Hendrik or KHAAS for E or step 6, read Vieze Jonge Pass and GWON.
- The Athanor is now named **"Orlov Mining Facility I"** (was De Kaasfabriek), at Piekura V - Moon 1.

### Owner's decisions (2026-10-05)
- **No public timers.** Only the own moon in Piekura is tracked; runbook 07 section F is marked not used.
- **Pings:** `@here` one hour before the chunk arrives (rule 1 changed from no ping) and `@here` at arrival (rule 2, unchanged). A 24-hour reminder was asked for and then withdrawn; it was not created. **Superseded later the same day: no moon pings at all, see "Pings switched off" below.**
- **Wants a slash command** that lists the upcoming moon extractions on request → runbook 08.

### Done on the server
- Owner confirmed the three test messages arrived in Discord.
- **E1–E2 (owner, browser)** with Vieze Jonge Pass. Verified: structures Owner 1 (GWON), active, both default webhooks attached; Structure 2 (Athanor "Orlov Mining Facility I" in Piekura, fuel until 2026-11-19 12:00 UTC; Raitaru "Orlov Family Facilities" in Isikano, fuel until 2026-11-06 14:00 UTC); moonmining Owner 1, Refinery 1, Extraction 1 (started 2026-10-04 07:08 UTC, **chunk arrives 2026-10-10 17:01 UTC**, auto fracture 20:01 UTC, status started — it survived the transfer).
- structures Notification 120, all history; only the 2 `StructuresReinforcementChanged` from 2026-10-04 were sent to Discord. 0 `Moonmining…` notifications (the extraction started under KHAAS).
- **structuretimers writes (announced, via Django):** rule 1 `ping_type` PN → PH; Timer pk 1 created for the current extraction (Athanor, Moon Mining, Piekura, 2026-10-10 17:01 UTC, objective friendly, user `tony`). Scheduled notifications now exist for 16:01 (rule 1) and 17:01 (rule 2) UTC on 2026-10-10.
- **G:** backup `~/backups/aa-db-2026-10-05-1028.sql.gz` ("backup ok", 4.3M), taken before the two structuretimers writes above. Config check at that time: server `conf/requirements.txt` had the same four package lines as `deploy/`; in `conf/local.py` the Day 5 block was byte-identical to `deploy/conf/local.py.append`, Member Audit schedule 3600, earlier blocks differ in comment lines only.

### Day 6 on the server (done 2026-10-05, about 10:53–11:05 UTC)
- Owner did section A (intents).
- Backup `~/backups/aa-db-2026-10-05-1053.sql.gz`; copies `requirements.txt`, `local.py`, `celery.py`, `docker-compose.yml` with suffix `.pre-day6` in `~/backups`.
- `~/aa-docker/orlovbot/` created from `deploy/orlovbot/` (Unix line endings; `git archive` on the PC exports CRLF, so the files were converted on the server).
- `conf/requirements.txt` + `allianceauth-discordbot==5.0.1`; `conf/local.py` + Day 6 block (byte-identical to the repo block, file now 187 lines); `conf/celery.py` + route `aadiscordbot.tasks.*` → queue `aadiscordbot` inside the existing dictionary, `discord.*` route kept; `docker-compose.yml` + volume `./orlovbot:/home/allianceauth/myauth/orlovbot` in the base block and service `allianceauth_discordbot`.
- Build exit 0. In a throwaway container: `check` no issues, `orlovbot.cogs.moons` imports (aadiscordbot 5.0.1, py-cord 2.8.1), hook returns it. `migrate` applied 17 `aadiscordbot` migrations. `up -d` recreated gunicorn, beat and the three workers and started the bot; nginx restarted; `collectstatic` copied 119 files.
- After: site 200, 11 containers up, workers healthy, no errors in the Alliance Auth containers. Bot output: "Authbot Started with command prefix !" and nothing else. Its INFO lines go nowhere (no logging handler for `aadiscordbot` configured), so login and command registration are not yet proven; section D proves them.

### Pings switched off (owner's decision, 2026-10-05 about 11:35 UTC)
- With the board live the owner wants **no moon pings** and removes the `#moon-timers` channel (which also deletes its Discord webhook).
- Server, via Django, rows kept: structuretimers `NotificationRule` pk 1 and 2 `is_enabled` False, `DiscordWebhook` pk 1 `is_enabled` False, the 2 scheduled notifications for 2026-10-10 removed; structures `Webhook` pk 1 "Moon Timers" `is_active` False and `is_default` False and detached from owner GWON. structures `Webhook` pk 2 "Structure Alerts" (`#directors`) is untouched and still attached.
- Timer pk 1 stays on the Structure Timers page on auth; it no longer triggers anything.
- To bring pings back: new channel webhook URL into the two "Moon Timers" webhook rows, re-enable them and the rules, re-attach the structures webhook to the owner.

### Structure board (runbook 10, done 2026-10-05 11:40 UTC)
- Owner's wish: the same dashboard style for directors, `#structure-board`, with war status, fuel, structure state and if possible the profile.
- New code: `orlovbot/board.py` (shared find/post/edit of a board message; the moon module now uses it too) and `orlovbot/cogs/structures.py`. `auth_hooks.py` registers both modules. Server folder replaced from the repo (old copy: `~/backups/orlovbot.pre-structure-board`); `conf/local.py` + "Structure board" block (now 200 lines; copy from before: `~/backups/local.py.pre-structure-board`). Only the bot was restarted.
- Bot output after restart: four modules loaded, "Upcoming moon extractions: found the board message in #moon-board", "Structure status: board posted in #structure-board" (the owner had already created the channel).
- Data sources: aa-structures models for state, power mode, fuel, services; public ESI `corporations/{id}` for `war_eligible` (GWON: true); wars reconstructed from the owner's stored war notifications (self-test on history: the 2025-10-09 declaration by Bully Brigade shows as running on 2025-10-10 and gone on 2025-10-12; none now); authenticated ESI `corporations/{id}/structures` with the existing structures token for `profile_id` (243511 Raitaru, 244593 Athanor). ESI gives no profile names, so `ORLOVBOT_STRUCTURE_PROFILES` maps number to name; it is empty until the owner supplies the names.
- Why not the ESI war list: `/wars/` has no per-corp filter and the sampled IDs were not in date order, so scanning it is neither cheap nor reliable.
- The bot's Discord role is `Orlov auth` (the only managed role).
- **Alerts (owner's request, deployed 11:53 UTC):** `@everyone` messages in `#structure-board` for a new war (once), and per structure once every 24 h while fuel is under 7 days (or gone with low power) or a service is offline. A new reminder replaces the old one; fixed problems remove their alert. Sent-state lives in the Django cache under `orlovbot:structure-board:alerts` (written before sending, so a restart cannot re-ping). Settings `ORLOVBOT_STRUCTURE_ALERTS` and `ORLOVBOT_STRUCTURE_ALERT_MENTION` appended to `conf/local.py` (205 lines; copy from before: `~/backups/local.py.pre-structure-alerts`). `plan_alerts()` self-tested with 13 synthetic scenarios, all pass. One live test alert was queued via the cache key `orlovbot:structure-board:test`; bot output: "Structure alert sent: test". The bot removes it at its next check; the owner has not yet confirmed seeing the ping.
- Owner's follow-up: fuel shows as "32 days left" instead of Discord's "in a month", with the run-out date as hover text. Discord only has hover text on links, so the amount is a masked link to `SITE_URL/structures/` with the date as link title (deployed 11:42 UTC).

### Moon board (runbook 09, done 2026-10-05 11:27 UTC)
- Owner's wish: an always-visible, self-updating list in Discord instead of asking with `/moons`. Chosen design: the bot posts one message in `#moon-board` and edits it in place (checks every 10 minutes, edits only on change; countdowns are Discord live timestamps). Discord Events, a channel-name ticker and aa-opcalendar were considered and not used.
- Server: `orlovbot/cogs/moons.py` replaced (copy of the old one: `~/backups/moons.py.pre-board`); `conf/local.py` + "Moon board" block (`ORLOVBOT_MOON_BOARD_CHANNEL = "moon-board"` and console logging for the `aadiscordbot` and `orlovbot` loggers; file now 194 lines; copy from before: `~/backups/local.py.pre-board`). Only the bot container was restarted.
- **The bot is now proven connected:** its output shows `on_ready Complete!`, the three loaded modules including `orlovbot.cogs.moons`, then the warning "no text channel named #moon-board yet". The board appears within 10 minutes of the owner creating the channel.
- Bot output is now readable with `docker compose logs allianceauth_discordbot`.

### Prepared in the repo for Day 6
- `docs/runbooks/08-day-six-moons-command.md`.
- `deploy/orlovbot/` — a small Django app with one command module, `cogs/moons.py` (`/moons`, restricted to the Discord role `Family Member`, reads `moonmining.Extraction`). Syntax-checked only; it has never run.
- `deploy/conf/requirements.txt` now also lists `allianceauth-discordbot==5.0.1`, and `deploy/conf/local.py.append` ends with a Day 6 block. The server now has both.
- Facts checked for the design: Alliance Auth 5.4.0, Django 5.2.17, Python 3.12 on the server; allianceauth-discordbot 5.0.1 requires `allianceauth<6,>=3` and py-cord 2; none of the installed apps registers a `discord_cogs_hook`; the bot loads modules from that hook in addition to `DISCORD_BOT_COGS`; server `conf/celery.py` already has an `app.conf.task_routes` dictionary with the `discord.*` route, so the add-on's route must be added inside it.
- aa-structuretimers reminder offsets: the admin offers 0 to 120 minutes only, but the code subtracts any number of minutes, so a longer offset would work if set through Django. Not used.

### Owner does by hand
- Runbook 09 section C: look at the board message in `#moon-board` and confirm it is right.
- Runbook 10 sections C and D: confirm `#structure-board` (and that only directors see it), and say which profile name belongs to which structure. Confirm the test ping arrived.
- Optional Discord clean-up found while listing what Family Friend can do: the `@everyone` role has "Mention @everyone" on (any visitor can ping the server from `#public-chat`); `#how-to-get-roles` and `#moon-board` still allow creating threads.
- Runbook 08 section D: type `/moons` in `#general`.

### Next — local session, after the owner reports on D
- If `/moons` answers: tick D in runbook 08, done. If it does not show or errors: runbook 08 Troubleshooting; read `docker compose logs --tail 50 allianceauth_discordbot`.
- After the owner confirms the board: tick runbook 09 C. On 2026-10-10 after 17:01 UTC check the board switched to "Chunk has arrived". No pings are expected.

### Open
- Tavaga's Discord ticker (showed STI on 2026-10-03) was never checked on the server.

### Notes for the local session
- Piping a script to `ssh` from PowerShell 5.1 prepends a byte-order mark and Python rejects it. Pipe from Git Bash through Windows OpenSSH instead: `cat script.py | /c/Windows/System32/OpenSSH/ssh.exe orlov "..."`.

---

## 2026-10-05 — local session (PC) → cloud session

**Runbook:** `docs/runbooks/07-day-five-moon-timers.md` — section C done via Django. **E is next (owner, browser).**

### Done (local, on the server)
- **C1, aa-structures webhooks:** "Moon Timers" (pk 1, the 5 `Moonmining…` types) and "Structure Alerts" (pk 2, the 16 types starting with `Structure`). Both active, default, language `en`.
- **C2, aa-structuretimers:** `DiscordWebhook` "Moon Timers" (pk 1, enabled). Two `NotificationRule` rows, both enabled, trigger "Scheduled time reached", require timer type Moon Mining only: pk 1 at T-60 with no ping, pk 2 at T-0 with `@here`. No "new timer created" rule.
- **Test messages:** all three webhooks returned success (two posts to `#moon-timers`, one to `#directors`). Owner has not yet confirmed seeing them in Discord.
- The owner pasted the webhook URLs in the local chat. They are stored in the auth database (admin → Structures → Webhooks, admin → Structure Timers → Discord webhooks) and are **not** in the repo.

### Finding — repo is public
- `github.com/Tony-carboni/Orlov` answers anonymously (HTTP 200 from the GitHub API without login), so it is **public**. The owner asked to save the webhook URLs in the repo; the local session did not, because anyone could then post in `#directors` and `#moon-timers` as the bot. Open decision for the owner: make the repo private (then the URLs can be committed if still wanted), or keep them in Bitwarden and the auth admin only. Note the repo also publishes the server IP and SSH username in `CLAUDE.md`.

### Owner does by hand (browser)
- Confirm the three test messages arrived in Discord.
- **E:** log out and in once on auth, then Structures → Add Owner and Moon Mining → Add Owner, both with Flapoor Hendrik.

### Next — local session, after the owner reports E done
- Step 6 of the 14:40 UTC cloud entry below: verify structures Owner (1, KHAAS) with both default webhooks attached, the Athanor and its fuel expiry, moonmining Owner/Refinery/Extraction (chunk arrival), the Moon Mining timer on the board (if 0 after 15 min, see runbook Troubleshooting), and the Moonmining notifications and whether they were sent.
- Rest of G: backup, confirm server `conf/requirements.txt` and `conf/local.py` match `deploy/`.

---

## 2026-10-04 (14:26 UTC, PC clock) — local session (PC) → cloud session

**Runbook:** `docs/runbooks/07-day-five-moon-timers.md` — section D done, Member Audit schedule fixed. **Section C not started** (waiting for the two webhook URLs), E and the rest of G still open.

### Done (local, on the server)
- **D, permissions (add-only):** Family Member 2 → 5, Alliance Director 10 → 22, Corp Director 4 → 7.
  - Family Member (**state**): moonmining `basic_access`, `extractions_access`; structuretimers `basic_access`.
  - Alliance Director (group): those three, plus moonmining `add_refinery_owner`, `view_moon_ledgers`, `reports_access`; structures `basic_access`, `add_structure_owner`, `view_all_structures`, `view_structure_fit`; structuretimers `create_timer`, `manage_timer`.
  - Corp Director (group): structures `basic_access`, `view_corporation_structures`; structuretimers `create_timer`.
- **Member Audit schedule (memberaudit.W001):** `memberaudit_run_regular_updates` is now `3600` seconds in server `conf/local.py` (line 122) and in `deploy/conf/local.py.append`. Copy of the file from before: `~/backups/local.py.pre-memberaudit-schedule`. `manage.py check` reports no issues.
- Restarted beat, then gunicorn and the three workers (see the bind-mount note below). Site answers 200, all containers up, workers healthy.
- Repo: runbook 07 section D corrected, deploy file updated — commit `856017a`.

### Differences from the handoff / things learned
- **`Family Member` is a state, not a group.** Groups are Alliance Director, Corp Director, FC, corp_FNA, corp_OARMI, corp_STI. State permissions live at `/admin/authentication/state/` and use Alliance Auth's proxy model `authentication.Permission` (look permissions up via `state.permissions.model`, not `auth.Permission`, or `.add()` raises a TypeError).
- **Structures `basic_access` was missing from the plan.** Without it the Structures page does not open, so it was added to both director groups. Family Member does not have it (members don't see Structures) — as designed in the runbook.
- **Model names for C:** aa-structuretimers' webhook model is `structuretimers.models.DiscordWebhook` (fields name, url, notes, is_enabled; method `send_test_message`; task `send_test_message_to_webhook(webhook_pk, user_pk)`). `NotificationRule`: trigger `TR` = scheduled time reached, `scheduled_time` 60 and 0, `ping_type` `PN` none / `PH` @here, `require_timer_types` `["MM"]`. aa-structures `Webhook`: fields name, url, notes, webhook_type (1 = Discord), is_active, notification_types, language_code, is_default, has_default_pings_enabled, ping_groups; task `send_test_notifications_to_webhook(webhook_pk, user_pk)`.
- **Notification types for "Structure Alerts"** (16 values start with `Structure`): Anchoring, Destroyed, FuelAlert, JumpFuelAlert, LostArmor, LostShields, LowReagentsAlert, NoReagentsAlert, Online, RefueledExtra, ServicesOffline, Unanchoring, UnderAttack, WentHighPower, WentLowPower, plus `StructuresReinforcementChanged`. The five `Moonmining…` values are as the runbook lists them.
- **Single-file bind mount:** `conf/local.py` is mounted as one file. Editing it with `sed -i` replaces the file, and running containers keep the old copy until they restart. Appending with `>>` keeps the same file. After any `sed -i` edit, restart every container that mounts it (gunicorn, beat, workers), not just the one that needs the change.
- **Local-session permissions:** the app's Auto mode refused the permission grant; it went through after the owner explicitly told the session to proceed. Server writes need the owner's explicit go-ahead in chat or Manual mode.

### Open
- **C (webhooks + rules):** the local session asked the owner to paste the two webhook URLs (`#moon-timers` "Moon Timers", `#directors` "Structure Alerts"); the owner accepted pasting them in chat (low stakes) but has not done so yet. Either the owner pastes them in the local session and it does C via Django as specified in the previous entry, or the owner does C in the browser per the runbook with the cloud session. Currently 0 structures webhooks, 0 structuretimers webhooks, 0 rules.
- **E (owner, browser):** log out and in once on auth, then Structures → Add Owner and Moon Mining → Add Owner with Flapoor Hendrik. **Do C1 first:** aa-structures attaches the default webhooks to an owner when the owner is created, so an owner added before the webhooks exist gets none and would have to be linked by hand in the admin (Structures → Owners → webhooks).
- **After E (local session):** step 6 of the previous entry (verify owners, Athanor, extraction, timer, notifications) and the rest of G (backup, verify server matches `deploy/`).

---

## 2026-10-04 (14:40 UTC) — cloud session → local session

**Runbook:** `docs/runbooks/07-day-five-moon-timers.md` — sections C and D moved to the local session (database rows, no browser needed). E stays with the owner (SSO login).

### Status
- Owner reports A1–A3 done (Flapoor Hendrik on the `tony` account, `#moon-timers` created, two webhook URLs saved in Bitwarden).
- Section B done (previous entry). Task queue empty.

### Next — local session: do runbook 07 sections C and D via Django, then hand E to the owner
All through `docker compose exec -T allianceauth_gunicorn python /home/allianceauth/myauth/manage.py shell` with a script on stdin. Announce each write first, one at a time, show results. Never echo the webhook URLs back into chat, logs, or files; never commit them.
1. Ask the owner to paste the two Discord webhook URLs into this chat: one for `#moon-timers` (name "Moon Timers"), one for `#directors` (name "Structure Alerts"). Treat them as secrets.
2. C1, aa-structures: inspect `structures.models.Webhook` fields and the notification type choices (`structures.core.notification_types.NotificationType` or the field's choices). Create two webhooks: "Moon Timers" with every type whose value starts with `Moonmining` (ExtractionStarted, ExtractionFinished, AutomaticFracture, LaserFired, ExtractionCancelled); "Structure Alerts" with every type whose value starts with `Structure` (fuel alert, under attack, lost shields/armor, destroyed, low/high power, services offline, anchoring/unanchoring, reinforcement changed, refueled extra) — exclude Moonmining, sovereignty, orbital, tower, war and billing types. Both `is_active=True`, `is_default=True`, language `en`. Then send a test message through each (the model's test-message method, the one the admin action uses) and ask the owner to confirm both arrived in Discord.
3. C2, aa-structuretimers: create `structuretimers.models.Webhook` "Moon Timers" (same `#moon-timers` URL, enabled). Create two `NotificationRule` rows, both enabled, webhook = that one, require timer types = the Moon Mining type only, all other filters empty: rule 1 trigger = scheduled time reached, 60 minutes before, ping type none; rule 2 trigger = scheduled time reached, 0 minutes (at the time), ping type `@here`. Inspect the model's choice constants first (trigger, scheduled_time, ping_type, timer type code for moon mining) and use those, don't guess numbers. No "new timer created" rule.
4. D, permissions on the three groups, via `django.contrib.auth.models.Permission` looked up by `content_type__app_label` + `codename` (list the codenames of app labels `moonmining`, `structures`, `structuretimers` first and map by their descriptions):
   - Family Member: moonmining basic access, moonmining extractions access, structuretimers basic access.
   - Alliance Director: everything Family Member gets, plus moonmining add refinery owner, view moon ledgers, reports access; structures add structure owner, view all structures, view structure fittings; structuretimers create/edit own timers, manage (edit/delete any) timers.
   - Corp Director: structures view corporation structures, structuretimers create/edit own timers.
   Show the final permission list per group.
5. Verify: 2 structures webhooks, 1 structuretimers webhook, 2 notification rules, permission counts per group. Then tell the owner: "log out and in once on auth, then do runbook 07 section E (Structures → Add Owner, Moon Mining → Add Owner, both with Flapoor Hendrik)".
6. After the owner reports E done: check `structures` Owner rows (1, corp KHAAS), Structure rows (the Athanor, fuel expiry), `moonmining` Owner/Refinery/Extraction rows (chunk arrival time), `structuretimers` Timer rows (1 moon mining timer; if 0 after 15 min, say so — the "extraction started" notification may be too old, see runbook Troubleshooting), and the Notification rows for the Moonmining type and whether they were sent to the webhook. Report.
7. Section G: run `~/bin/aa-backup.sh`; confirm server `conf/requirements.txt` and the Day 5 block of `conf/local.py` match `deploy/`. Also fix the Member Audit warning memberaudit.W001: in both server `conf/local.py` and repo `deploy/conf/local.py.append`, change the `memberaudit_run_regular_updates` schedule from the crontab to `3600` (seconds), then `docker compose restart allianceauth_beat` and confirm `check` has no warning. Commit the repo change.
8. Write the next handoff entry (what was done, any model/field names that differed, E results), commit, push.
Rules from CLAUDE.md apply.
