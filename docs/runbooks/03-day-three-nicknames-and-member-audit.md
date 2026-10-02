# Day 3 runbook — `[OARMI]` nicknames and Member Audit

*Prerequisite: Day 2 complete (states, groups, Discord roles, Corp Stats working).*
*Time: ~1.5 hours, of which ~20 min is waiting for an image build and a data load. Sections A, C–E in the **browser**; B and F on the **server**.*
*Convention: one code block = one Enter. Blocks that must be pasted whole are labelled.*

**Goal:** members' Discord nicknames become `[OARMI] Character Name` automatically, and Member Audit gives you per-character login dates (your 60-day rule), skills, assets and a corp compliance view.

Decisions baked in (from `docs/design/membership.md`):
- Nicknames via Alliance Auth's built-in **name formatter** — no extra bot needed (the discordbot is deferred until there are members to use `/lookup`).
- Member Audit compliance groups stay **off** (alts encouraged, not required).

## Known values

| Item | Value |
|---|---|
| Server | `ssh tony@167.99.207.145` → `~/aa-docker` |
| Admin | https://auth.orlovfamily.space/admin/ |
| Package added | `aa-memberaudit==5.2.0` (pulls in `django-eveuniverse`) |
| Nickname format | `[{corp_ticker}] {character_name}` → `[OARMI] Tony Carboni` |

---

## A. Nickname format (browser)

**A1.** Open **https://auth.orlovfamily.space/admin/services/nameformatconfig/add/**:

| Field | Value |
|---|---|
| Service | `discord` |
| Format | `[{corp_ticker}] {character_name}` |
| States | select `Family Member` and `Family Friend` (Ctrl-click) |

**Save.** (One formatter per service per state — don't add a second one.)

## B. Enable nickname sync + build the custom image (server)

```bash
ssh tony@167.99.207.145
```

```bash
cd ~/aa-docker
```

**B1. Nickname sync back on** (activation for you already happened on Day 2, so the owner-403 no longer blocks anything; for you specifically the nickname won't auto-update — set it by hand in Discord):

```bash
sed -i 's/^DISCORD_SYNC_NAMES = False.*/DISCORD_SYNC_NAMES = True/' conf/local.py
```

```bash
grep -n DISCORD_SYNC_NAMES conf/local.py
```

✅ shows `DISCORD_SYNC_NAMES = True`.

**B2. Add the package** to the custom-image requirements:

```bash
echo "aa-memberaudit==5.2.0" >> conf/requirements.txt
```

```bash
cat conf/requirements.txt
```

**B3. Switch docker-compose.yml from the stock image to the custom build.** Lines 2–7 of the file are the `image:` line followed by a commented-out `build:` block; this comments line 2 and uncomments 3–7:

```bash
sed -i '2s/^  image:/  # image:/; 3,7s/^  # /  /' docker-compose.yml
```

```bash
head -8 docker-compose.yml
```

✅ Expected output (not a command — don't paste): line 2 reads `# image: ${AA_DOCKER_TAG?err}`; lines 3–7 read `build:`, `context: .`, `dockerfile: custom.dockerfile`, `args:`, `AA_DOCKER_TAG: ${AA_DOCKER_TAG?err}` with no `#`.

**B4. Member Audit settings** — **paste as one block** (ends at `PYEOF`):

```bash
cat >> conf/local.py <<'PYEOF'

# --- Member Audit (Day 3) --------------------------------------------------
INSTALLED_APPS += [
    "eveuniverse",   # EVE static data, required by memberaudit
    "memberaudit",
]
CELERYBEAT_SCHEDULE["memberaudit_run_regular_updates"] = {
    "task": "memberaudit.tasks.run_regular_updates",
    "schedule": crontab(minute="0", hour="*/1"),
}
PYEOF
```

```bash
tail -4 conf/local.py
```

**B5. Build and start.** The build downloads and compiles the package (~3–5 min):

```bash
docker compose --env-file=.env build
```

✅ ends with something like `=> exporting to image` / `Successfully built`, no red `ERROR`.

```bash
docker compose --env-file=.env up -d
```

(Recreates every auth container on the new image.)

**B6. Migrate, collect static, load EVE data:**

```bash
docker compose exec allianceauth_gunicorn bash
```

inside the container:

```bash
auth check
```

```bash
auth migrate
```

```bash
auth collectstatic --noinput
```

```bash
auth memberaudit_load_eve
```

It asks `Are you sure? (y/N)` → `y`. This *queues* background tasks that pull ship/skill/type data from ESI and returns immediately; the workers need **10–20 minutes** to finish. Then:

```bash
exit
```

Watch progress from the dashboard's *Task Queue* panel (https://auth.orlovfamily.space/) — wait until *queued* is back to 0 before registering characters in E.

```bash
docker compose ps | grep -E "gunicorn|beat|worker"
```

✅ All `Up`. Left menu now has **Member Audit**.

## C. Permissions (browser)

Member Audit is permission-driven; nothing shows until these are set.

**C1. Every member may register their own characters** — https://auth.orlovfamily.space/admin/authentication/state/ → **Family Member** → Permissions → filter `memberaudit` → choose **memberaudit | general | Can access this app, register, and view own characters** → Save. Same for **Family Friend** (so blues can register if you ever ask them to).

**C2. Leadership views** — admin → Group Management → Groups:

| Group | Add permissions (all `memberaudit | general | …`) |
|---|---|
| `Alliance Director` | *Can view alliance characters*, *Can access reports feature*, *Can access character finder feature*, *Can view characters owned by others*, *Can view skill sets for a character* |
| `Corp Director` | *Can view corporation characters*, *Can access reports feature*, *Can view characters owned by others* |

Save each.

## D. Nickname check (browser + Discord)

Nickname sync applies on the next update for each user. Force one for yourself to confirm the formatter is accepted: admin → Discord Service → **Discord users** → tick your row → Action **Update nicknames** → Go.

- For **you** (server owner) this will log an error — expected; set your own nickname to `[OARMI] Tony Carboni` manually in Discord (right-click yourself → Edit Server Profile).
- For every other member it will "just work" when they activate Discord.

## E. Register your characters in Member Audit (browser)

https://auth.orlovfamily.space/memberaudit/ → **Register** (or *Add character*) → EVE SSO lists ~34 scopes → **Authorize** with your main. Repeat for each alt you want tracked (policy: alts encouraged, not required).

The first data pull per character takes a few minutes. Then:

- **Character viewer** → your main → *Character* tab shows **last login/logout** — this is the 60-day inactivity signal.
- **Reports** (leadership) → *Compliance* lists every corp member and whether their characters are registered; *Last login* columns appear as data arrives.

✅ Your main shows a last-login timestamp.

## F. Backup (server)

```bash
cd ~/aa-docker
```

```bash
docker compose exec -T auth_mysql sh -c 'exec mariadb-dump --all-databases -uroot -p"$MYSQL_ROOT_PASSWORD"' | gzip > ~/backups/aa-$(date +%F).sql.gz
```

```bash
ls -lh ~/backups
```

---

## Day 3 completion checklist

- [ ] Name format config exists for Discord: `[{corp_ticker}] {character_name}`
- [ ] `docker compose ps` — all Up on the custom image; `conf/requirements.txt` has `aa-memberaudit==5.2.0`
- [ ] Member Audit in the left menu; your main registered; last-login visible
- [ ] Permissions set on `Family Member`, `Alliance Director`, `Corp Director`
- [ ] Your Discord nickname set manually to `[OARMI] …`
- [ ] Fresh DB dump

**Next:** Day 4 — operations: nightly backup cron, off-box backup copy, the update procedure for AA and packages, and the CEO onboarding runbook (Corp Stats + Member Audit director token) for when the first corp joins. The discordbot (`/lookup`, tickets) comes once there are members to use it.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `build` fails with pip resolution error | Check the exact line in `conf/requirements.txt`; `aa-memberaudit==5.2.0` requires AA 4–5 (we run 5.4.0). Paste the last 20 lines of the build output. |
| `auth check` complains about `eveuniverse` | `INSTALLED_APPS` order matters: `eveuniverse` must be listed before `memberaudit` (it is in B4). |
| Member Audit page says "no access" | C1 permission missing on your state, or you're not in `Family Member`. |
| Register fails at SSO with "invalid scope" | The EVE developer application must have all `esi-*` scopes ticked (Day 0 step E2). Edit the app on developers.eveonline.com and tick them. |
| Characters never update | Check dashboard *Task Queue* for failures; `docker compose logs --tail 100 allianceauth_worker` for `memberaudit` errors. |
| Nicknames don't change for members | Name format config missing the member's **state**, or `DISCORD_SYNC_NAMES` still `False`. Updates happen on activation and on main-character changes; force via admin → Discord users → *Update nicknames*. |
| Nickname error for you only | Server owner — expected. Set manually. |
