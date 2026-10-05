# Day 6 runbook — `/moons` slash command in Discord

*Prerequisite: Day 5 (runbook 07) complete: Moon Mining shows the extraction of our Athanor.*
*Time: ~30 min. You do section A (browser, 2 min) and section D (Discord, 2 min). Sections B and C are run by Claude in the **local session** (say "run Day 6 section B").*

**Goal:** any Family Member types `/moons` in Discord and gets the list of upcoming moon extractions (structure, moon, time until the chunk arrives, EVE time and their own local time).

Decisions baked in:
- None of the installed apps ships a Discord command, so this needs the bot add-on **allianceauth-discordbot** (5.0.1, supports Alliance Auth 3 to 5) plus a small command of our own, kept in `deploy/orlovbot/` in this repo.
- The bot runs as one extra container, `allianceauth_discordbot`, and logs in with the **same bot** that already manages roles and nicknames. No new Discord application, no new token.
- Only three commands are switched on: `/moons` (ours), `/time` and `/about`. The add-on's other modules (sov, price check, easter eggs, tickets, ...) stay off.
- `/moons` answers only people who hold the `Family Member` role; everyone else gets a private "members only" reply. It reads our own extractions from Moon Mining, so no public timers.
- Pings stay as set on Day 5: `@here` one hour before the chunk arrives and `@here` when it arrives. No 24-hour reminder.

## Known values

| Item | Value |
|---|---|
| Package | `allianceauth-discordbot==5.0.1` |
| Our command code | `deploy/orlovbot/` in the repo → `~/aa-docker/orlovbot/` on the server |
| New container | `allianceauth_discordbot` (runs `manage.py run_authbot`) |
| Settings | Day 6 block at the end of `deploy/conf/local.py.append` |

---

## A. Allow the bot to see members and messages (browser, 2 min)

1. Open https://discord.com/developers/applications and pick the application you created on Day 0 (the one whose bot is in the server).
2. Left menu **Bot** → scroll to **Privileged Gateway Intents**.
3. Switch on **Server Members Intent** and **Message Content Intent** (Presence Intent may stay off).
4. **Save Changes**.

✅ Done when both switches are on and saved. Without this the bot container starts and stops again with a "privileged intents" error.

## B. Install the bot (server — local session)

*Done 2026-10-05 by the local session: backup `aa-db-2026-10-05-1053.sql.gz`, image rebuilt, 17 `aadiscordbot` migrations applied, 11 containers up, site answers 200. Order used: build first, then `check`, the import test and `migrate` from a throwaway container, then `up -d`. Lesson: do steps 3 to 6 and the build without pausing, because once `local.py` names the new apps a container that restarts on the old image would fail.*

The local session does this, announcing each change first. For reference, the steps are:

1. Backup with `~/bin/aa-backup.sh`; keep copies of `conf/requirements.txt`, `conf/local.py`, `conf/celery.py` and `docker-compose.yml` in `~/backups` (suffix `.pre-day6`).
2. Copy `deploy/orlovbot/` from the repo to `~/aa-docker/orlovbot/`.
3. `conf/requirements.txt`: add the package line so the file matches `deploy/conf/requirements.txt`.
4. `conf/local.py`: append the Day 6 block from `deploy/conf/local.py.append` (from the comment line "# --- Day 6" to the end). Append with `>>`, never `sed -i` (single-file bind mount, see the Day 5 handoff notes).
5. `conf/celery.py`: add the route `"aadiscordbot.tasks.*": {"queue": "aadiscordbot"}` **inside** the existing `app.conf.task_routes` dictionary, next to the `discord.*` line. Do not paste the add-on's README snippet as it stands: it replaces the whole dictionary and would drop the `discord.*` route.
6. `docker-compose.yml`: add `- ./orlovbot:/home/allianceauth/myauth/orlovbot` to the `volumes` of the `x-allianceauth-base` block, and add the service `allianceauth_discordbot` after `allianceauth_worker_services`: container name `allianceauth_discordbot`, the same `<<: [*allianceauth-base]` merge as the other Alliance Auth services, `restart: on-failure`, entrypoint `python -u /home/allianceauth/myauth/manage.py run_authbot`.
7. Build the image, then run `manage.py check` in a throwaway container from the new image **before** touching the running stack. A wrong setting or an import error in `orlovbot` would otherwise stop every Alliance Auth container.
8. `docker compose --env-file=.env up -d`, restart nginx, `manage.py migrate` (the add-on has its own tables), `collectstatic --noinput`.

✅ Done when the site answers 200, all containers are up (now 11), and `docker compose logs allianceauth_discordbot` shows the bot logged in with no traceback.

## C. Check the command is registered (server — local session)

*Checked 2026-10-05 before start-up: in a throwaway container the module `orlovbot.cogs.moons` imports cleanly and the hook returns it. The running bot prints only "Authbot Started" and no errors; its informational log lines are not written anywhere yet (no log handler for `aadiscordbot`), so the real proof is section D.*

If the bot's output (`docker compose logs allianceauth_discordbot`) shows an error for that module, the rest of the bot still runs: the local session fixes the file in `~/aa-docker/orlovbot/` (and in `deploy/orlovbot/`) and restarts only the bot container.

## D. Try it (Discord, 2 min)

1. In `#general` (not `#moon-timers`, which is read-only for members), type `/moons` and pick the command from the popup.
2. ✅ The bot answers with "Upcoming moon extractions" and one entry: Orlov Mining Facility I, Piekura V - Moon 1, the time until the chunk arrives, the EVE time and your local time.
3. Ask someone with only `Family Friend` to try: they get a private "This command is for Family Members." reply.

## Day 6 completion checklist

- [x] Server Members and Message Content intents switched on (A)
- [x] Bot container running, command module loaded (B, C)
- [ ] `/moons` answers in Discord (D)
- [x] Backup taken, server matches `deploy/` (B1, end of B)

## Troubleshooting

- **`/moons` does not show up in the command popup** → wait a minute and restart Discord (Ctrl+R); commands are registered per server and normally appear at once. If it still does not show, the bot was invited without the "application commands" permission: re-authorise it from the Developer Portal (**OAuth2 → URL Generator**, tick `bot` and `applications.commands`, open the URL, pick the server). This does not remove the bot or its roles.
- **Bot container keeps restarting, log says "PrivilegedIntentsRequired"** → section A was not saved.
- **"The application did not respond"** → the command raised an error; the local session reads `docker compose logs --tail 50 allianceauth_discordbot`.
- **Roles or nicknames stop syncing after the install** → the `discord.*` route was lost from `conf/celery.py` (step B5); restore it from `~/backups/celery.py.pre-day6`.
- **Everything is down after `up -d`** → step B7 was skipped; restore the four `.pre-day6` files and run `up -d` again.

**Next:** when the next extraction is started under GWON, check that its timer and the "Extraction started" post appear on their own, and that `/moons` lists it.
