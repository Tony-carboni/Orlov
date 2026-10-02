# Day 4 runbook — operations: backups, updates, housekeeping

*Prerequisite: Day 3 complete.*
*Time: ~45 min. Sections A–C on the **server**; D in the DigitalOcean panel. No browser work in auth today.*
*Convention: one code block = one Enter. Blocks that must be pasted whole are labelled.*

**Goal:** the stack survives mistakes and server loss without you remembering to do anything: nightly database + config dumps kept 14 days, weekly whole-server snapshots at DigitalOcean, and a written, tested update procedure.

## Known values

| Item | Value |
|---|---|
| Server | `ssh tony@167.99.207.145` |
| Stack | `~/aa-docker` (`.env`, `conf/`, `docker-compose.yml` are the only hand-made files) |
| Dumps | `~/backups/` |
| Data that matters | MariaDB (everything: users, tokens, groups, Member Audit), `.env` (secrets), `conf/local.py`, `conf/requirements.txt` |
| Already handled by the stack | Docker log rotation (50 MB × 5 per container), container auto-restart, Ubuntu security updates (unattended-upgrades) |

---

## A. Nightly backup script (server)

```bash
ssh tony@167.99.207.145
```

```bash
mkdir -p ~/bin ~/backups
```

**A1. Create the script** — **paste as one block** (ends at `SHEOF`):

```bash
cat > ~/bin/aa-backup.sh <<'SHEOF'
#!/bin/bash
# Nightly Alliance Auth backup: DB dump + config tarball, keep 14 days.
set -e
cd "$HOME/aa-docker"
mkdir -p "$HOME/backups"
stamp=$(date +%F-%H%M)
docker compose exec -T auth_mysql sh -c 'exec mariadb-dump --all-databases -uroot -p"$MYSQL_ROOT_PASSWORD"' | gzip > "$HOME/backups/aa-db-$stamp.sql.gz"
tar czf "$HOME/backups/aa-config-$stamp.tgz" .env conf docker-compose.yml
find "$HOME/backups" -name 'aa-*' -mtime +14 -delete
echo "$(date '+%F %T') backup ok: aa-db-$stamp.sql.gz"
SHEOF
```

```bash
chmod +x ~/bin/aa-backup.sh
```

**A2. Test it once by hand:**

```bash
~/bin/aa-backup.sh
```

```bash
ls -lh ~/backups
```

✅ A new `aa-db-<date>-<time>.sql.gz` (a few MB) and `aa-config-<date>-<time>.tgz` (a few KB), and the line `backup ok`.

**A3. Schedule it nightly at 03:30 UTC** (quiet hour; EVE downtime is 11:00 UTC):

```bash
(crontab -l 2>/dev/null; echo "30 3 * * * $HOME/bin/aa-backup.sh >> $HOME/backups/backup.log 2>&1") | crontab -
```

```bash
crontab -l
```

✅ One line ending in `aa-backup.sh >> … backup.log 2>&1`. Tomorrow, `cat ~/backups/backup.log` should show a `backup ok` line.

**A4. Restore procedure — ⚠️ REFERENCE ONLY, do not run today.** (Replace `<stamp>` with a real file name when the day comes, and run it from `~/aa-docker`.) With a dump file and the config tarball you can rebuild on any server: Day 1 sections B–D on a fresh VPS (skip `prepare-env.sh`; instead `tar xzf aa-config-….tgz` into `~/aa-docker`), start the stack, then load the dump:

```bash
gunzip -c ~/backups/aa-db-<stamp>.sql.gz | docker compose exec -T auth_mysql sh -c 'exec mariadb -uroot -p"$MYSQL_ROOT_PASSWORD"'
```

then `docker compose restart` and point DNS at the new IP. Members notice nothing; tokens survive because `.env` carries the same `AA_SECRET_KEY`.

## B. Off-server copy (DigitalOcean panel + PC)

Local dumps don't help if the Droplet is lost. Two layers, both cheap:

**B1. DigitalOcean Backups** — cloud.digitalocean.com → Droplets → `ubuntu-s-2vcpu-4gb-lon1` → **Backups** tab → **Enable Backups** (weekly, $4.80/mo = 20 % of the Droplet). Whole-disk snapshot, restorable in one click. That's the "server died" case.

**B2. Monthly copy to your PC** (the "DigitalOcean account died" case). On your **PC**, PowerShell, once a month:

```powershell
scp "tony@167.99.207.145:backups/aa-db-*.sql.gz" "$HOME\Downloads"
```

(That's for **PowerShell**. In a plain *Command Prompt* window `$HOME` doesn't exist — use `"%USERPROFILE%\Downloads"` instead.)

Then move the newest one somewhere that isn't `Downloads`. Along with the `.env` already in Bitwarden, that's a complete off-site copy.

## C. Update procedure (server) — monthly, or when a security release lands

Alliance Auth announces releases on its Discord and GitLab; Member Audit on GitHub. Read the changelog first; if it says "breaking" or "run X before upgrading", ask before proceeding.

**C1. Fresh backup first:**

```bash
~/bin/aa-backup.sh
```

**C2. Alliance Auth itself** — the version is the tag in `.env`:

```bash
grep AA_DOCKER_TAG ~/aa-docker/.env
```

To move to a newer release, change the version at the end of that line with `nano ~/aa-docker/.env` — **only to a version that exists** (check https://pypi.org/project/allianceauth/ — the number at the top is the latest). Don't change it when there is nothing newer.

**C3. Extra packages** — only when https://pypi.org/project/aa-memberaudit/ shows a newer version, change the pin in `conf/requirements.txt`:

```bash
nano ~/aa-docker/conf/requirements.txt
```

**C4. Rebuild and roll out** (works for C2, C3 or both):

```bash
cd ~/aa-docker
```

```bash
docker compose --env-file=.env build --pull
```

```bash
docker compose --env-file=.env up -d
```

```bash
docker compose restart nginx
```

```bash
docker compose exec allianceauth_gunicorn bash
```

inside the container:

```bash
allianceauth update myauth
```

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
exit
```

✅ https://auth.orlovfamily.space loads; dashboard *Software Version* shows the new number; Task Queue has 0 failed.

**C5. If it went wrong** — roll back the version in `.env` / `requirements.txt`, repeat C4. If the database migrated forward and the old version refuses to start, restore the C1 dump (A4).

**Reminder:** a Claude routine named *Orlov monthly ops reminder* runs on the 1st of each month (08:51 Brussels) and emails/pushes this checklist with current-vs-latest version numbers. Manage it under *Routines* in claude.ai.

## D. Housekeeping (server) — monthly, 5 minutes

Ubuntu security patches install themselves; everything else is this:

```bash
sudo apt update && sudo apt -y upgrade
```

If it prints `*** System restart required ***` (or `/var/run/reboot-required` exists):

```bash
sudo reboot
```

Containers come back on their own (`restart: always`); wait 2 min, then check the site.

Reclaim disk from old images after rebuilds:

```bash
docker image prune -f
```

```bash
df -h /
```

✅ Root disk well under 80 %.

---

## Day 4 completion checklist

- [ ] `~/bin/aa-backup.sh` exists, ran once by hand, `crontab -l` shows the 03:30 line
- [ ] Tomorrow: `~/backups/backup.log` has a `backup ok` line
- [ ] DigitalOcean weekly Backups enabled
- [ ] One dump copied to your PC
- [ ] Section C read once, so the first real update isn't the first time you see it

**Next:** two documents that aren't runbooks for you but for others — the **member guide** for `#how-to-auth` and the **corp CEO onboarding** sheet — both in `docs/guides/`. Then, when members arrive: discordbot (`/lookup`, tickets).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `backup.log` shows `permission denied` / `docker: not found` | cron runs with a minimal PATH; the script uses `docker compose` from `/usr/bin` which is on it — but if not, add `PATH=/usr/local/bin:/usr/bin:/bin` as the first line of `crontab -e`. |
| Dump is suspiciously small (< 500 KB) | MariaDB wasn't up; `docker compose ps auth_mysql`. |
| After an update: 502 | `docker compose restart nginx` (stale upstream IP). |
| After an update: `auth migrate` errors | Paste the error; usually a package needs a specific AA version — check its changelog, pin the older version, rebuild. |
