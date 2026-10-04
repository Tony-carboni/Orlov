# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

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
- **E (owner, browser):** log out and in once on auth, then Structures → Add Owner and Moon Mining → Add Owner with Flapoor Hendrik. Can be done before C, but the "Extraction started" Discord post only goes out once the C1 webhook exists.
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

---

## 2026-10-04 (14:15 UTC) — local session (PC) → cloud session

**Runbook:** `docs/runbooks/07-day-five-moon-timers.md` — section B complete. Sections C–E are next (browser, owner + cloud session).

### Done (local, on the server)
- Backup before changes: `~/backups/aa-db-2026-10-04-1327.sql.gz` ("backup ok", exit 0). Copies of the pre-change config: `~/backups/requirements.txt.pre-day5`, `~/backups/local.py.pre-day5`.
- B1: `conf/requirements.txt` now has the four package lines (memberaudit 5.2.0, structures 4.0.4, moonmining 3.1.0, structuretimers 3.2.0).
- B2: Day 5 block appended to `conf/local.py` straight from `deploy/conf/local.py.append` (128 → 174 lines, syntax ok), so server and repo are identical for that block.
- B3: build exit 0, `up -d` recreated gunicorn, beat and the three workers, nginx restarted. Site answers (302 to login, login page 200).
- B4: `check` ok; `migrate` applied 24 migrations (moonmining 7, structures 9, structuretimers 8), all OK; `collectstatic` copied 119 files; all four data loads run.
- Verified at 14:10 UTC: task queue **0** (all priorities); eveuniverse has 114 regions, 1184 constellations, 8490 solar systems, **Piekura present**; 460 moonmining ore types; Athanor type present; the new periodic tasks are firing (structures fetch/update, moonmining regular updates, structuretimers dispatch); no errors in the container logs or `allianceauth.log` since rollout. Structures owners 0, webhooks 0, timers 0 — as expected before C–E.

### Differences from the runbook
- `eveuniverse_load_eve` does not exist; the command is **`eveuniverse_load_data map`**. Runbook B4 corrected. The map load finished in under 10 minutes, not 30–45.
- `structuretimers_load_eve` and `moonmining_load_eve` have no `--noinput`; `y` was piped on stdin. `structures_load_eve` and `eveuniverse_load_data` accept `--noinput`.
- `redis-cli llen celery` always reads 0 here: Alliance Auth splits the queue into priority keys. The real number is the sum over all `celery*` list keys (or the dashboard's Task Queue panel). Runbook troubleshooting updated.
- Extra safety step, not in the runbook: before `up -d`, `manage.py check` was run in a throwaway container from the new image (needs `--entrypoint python`, the image's entrypoint is gunicorn).

### Findings (not acted on)
- Django check warning **memberaudit.W001**: `CELERYBEAT_SCHEDULE["memberaudit_run_regular_updates"]` uses a crontab; Member Audit 5.2.0 wants a number of seconds (e.g. 3600). Dates from Day 3, harmless so far. Decide with the owner; fix needs an edit to `conf/local.py` + `deploy/conf/local.py.append` and a restart of beat.
- Server `conf/requirements.txt` has no comment header (the repo copy has two comment lines); package lines match.
- Local-session permissions: the app's Auto mode refuses state changes on the server ("Modify Shared Resources"). The owner switched this session to **Manual** mode and approves each command. Expect the same for future server work.

### Owner does by hand (browser) — status not confirmed
- A1: Add Character (Flapoor Hendrik) on the `tony` account + Member Audit registration.
- A2–A3: `#moon-timers`, the two webhooks, URLs in Bitwarden.

### Next — cloud session
The task queue is empty, so E is no longer blocked by the data load. Walk the owner through C (webhooks and rules), D (permissions) and E (register the Athanor) in the browser. Ask first whether A1–A3 are done. When E is finished, hand back to the local session for G (backup + verify server matches `deploy/`).

---

## 2026-10-04 — cloud session → local session

**Runbook:** `docs/runbooks/07-day-five-moon-timers.md` — section B (install the three apps).

### Done (cloud)
- Read the previous entry. Runbook 07 corrected: A1 now says the owner's auth account is `tony` (main Catherine Frey), warns against logging in as Flapoor Hendrik while logged out, and adds re-registering him in Member Audit. B4 notes the `manage.py` path for non-interactive use.
- `deploy/conf/requirements.txt` and `deploy/conf/local.py.append` already carry the Day 5 lines (block starts at the comment line "# --- Day 5: moon timers"). Use them as the source for the server edits so the two stay identical.

### Owner does by hand (browser), can run in parallel with section B
- A1: Add Character (Flapoor Hendrik) on the `tony` account, then Member Audit registration.
- A2–A3: create `#moon-timers`, two webhooks, save the URLs in Bitwarden.

### Next — local session: run runbook 07 section B
Context: install aa-structures 4.0.4, aa-moonmining 3.1.0, aa-structuretimers 3.2.0 into the custom image, exactly as runbook 07 section B describes. Announce each state change first, one at a time, show output. Steps:
1. Check the stack is up (compose ps). Run `~/bin/aa-backup.sh`; confirm by the printed "backup ok" and the new file in `~/backups`.
2. B1: append the three pinned package lines to `~/aa-docker/conf/requirements.txt` so it matches `deploy/conf/requirements.txt` in the repo (4 lines total; do not duplicate memberaudit). Show the file.
3. B2: append the Day 5 block from `deploy/conf/local.py.append` (from the line "# --- Day 5: moon timers" to the end of the file) to `~/aa-docker/conf/local.py`. Check first that `conf/local.py` does not already contain "structuretimers" (idempotent). Show the last 10 lines afterwards. Do not print any other part of local.py and never print .env.
4. B3: `docker compose --env-file=.env build` (takes ~5 min; report the tail of the output), then `docker compose --env-file=.env up -d`, then `docker compose restart nginx`. Confirm https://auth.orlovfamily.space answers 200 (curl -sI from the server or the PC).
5. B4, all via `docker compose exec -T allianceauth_gunicorn python /home/allianceauth/myauth/manage.py <cmd>`: `check`, `migrate`, `collectstatic --noinput`, `eveuniverse_load_eve map --noinput`, `structures_load_eve`, `structuretimers_load_eve`, `moonmining_load_eve`. If a load command has no `--noinput`, pipe `y` on stdin. Report what each printed.
6. Verify: compose ps shows gunicorn, beat, worker Up; the task queue is draining (`docker compose exec -T redis redis-cli llen celery` every few minutes until it trends down; the map load takes ~30–45 min). Report the queue length when you finish.
7. Write the next handoff entry (what was done, queue status, anything that differed from the runbook), commit, push. The owner then does sections C–E in the browser with the cloud session.
Rules from CLAUDE.md apply (backup first, no rm -rf, nothing in mysql-data/, never print .env).

---

## 2026-10-04 — local session (PC) → cloud session

**Runbook:** `docs/runbooks/07-day-five-moon-timers.md` — preparing the holding-corp CEO character.

### Done
- Stack checked: all 10 containers up, health-checked ones healthy.
- Backup before changes: `~/backups/aa-db-2026-10-04-1312.sql.gz` (script printed "backup ok", exit 0).
- **Flapoor Hendrik detached from the test user.** Deleted via Django ORM: CharacterOwnership pk 15, OwnershipRecord pk 15, esi Token pk 36 (scope `publicData` only). Verified 0 rows of each remain. His EveCharacter row is kept: pk 7, character_id 2117517330, corp "Kazen die stinken zijn lekkerder" [KHAAS], corp_id 98845682, no alliance.
- Test user (id 3, username `Flapoor_Hendrik`): main Gewoon Rudi, state Family Member, group `corp_OARMI`, owns only Gewoon Rudi. It was already in that state before the deletes; no main change or state check was needed. Gewoon Rudi's ownership (pk 16) and token untouched.

### Findings / corrections
- **There is no character "Tony Carboni" in auth.** The owner's account is user id 1, username `tony` (superuser), main **Catherine Frey**, 10 characters: Catherine Frey, Doe-het-zelf Roger, JFFUELFUND, Sorema Rinah, Tommy McPhee, Vieze Jonge Pass, carbondnb, fluorescent pony, lkdsfjmqsfd, phosphorescent pony. Fix the runbook wherever it names "Tony Carboni" as the main.
- The memberaudit Character for Flapoor Hendrik (pk 9) was **not** deleted by cascade: in this version it links to EveCharacter, not CharacterOwnership. It still exists, currently unowned.
- Other users: id 2 `Gewoon_Rudi` (no main, Guest, no characters — leftover empty user), id 4 `Nashomon_Yoma_Itinen` and id 5 `Tavaga` (Family Member), id 6 `Claudio_Madullier` (Family Friend).

### Owner still has to do (browser) — not confirmed done when this was written
1. Log in to auth as the `tony` account (e.g. with Catherine Frey). Not with Flapoor Hendrik while logged out — auth would create a new separate user for him.
2. Dashboard > Add Character > pick Flapoor Hendrik on EVE SSO.
3. Register Flapoor Hendrik in Member Audit again (his old token had only `publicData`).

### Next
Cloud session: continue Day 5 from the step after the character move, with Flapoor Hendrik as the holding-corp CEO character on the `tony` account. Ask the owner whether the three browser steps above are done.

### Notes for prompts aimed at the local session
- `auth shell` does not work through `docker compose exec` (no `auth` executable in the container). Use `python /home/allianceauth/myauth/manage.py shell` in the `allianceauth_gunicorn` container with `exec -T`, script piped on stdin.
- A manual run of `~/bin/aa-backup.sh` prints "backup ok" to the screen but does not append to `~/backups/backup.log` (only the 03:30 cron run does). Confirm manual backups by the printed line and the new file in `~/backups`.
- On the PC, Git Bash's `ssh` cannot read the `orlov-claude` key; the local session uses Windows OpenSSH (`ssh` from PowerShell).
