# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

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
