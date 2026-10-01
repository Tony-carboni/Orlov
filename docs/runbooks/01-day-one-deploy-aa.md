# Day 1 runbook — deploy Alliance Auth on auth.orlovfamily.space

*Prerequisite: Day 0 complete (server `167.99.207.145` with Docker, user `tony`; DNS `auth.orlovfamily.space` → server; EVE app with callback `https://auth.orlovfamily.space/sso/callback`; Bitwarden entry filled).*
*Time: 1–2 hours, mostly waiting for downloads. Everything in sections B–E is typed on the **server** (prompt `tony@ubuntu-...:~$`), except where it says "on your PC".*

Values used throughout (from Day 0):

| Item | Value |
|---|---|
| Site name | `The Orlov Family` |
| Base domain | `orlovfamily.space` |
| Auth subdomain | `auth` → `https://auth.orlovfamily.space` |
| Server user | `tony` |
| From Bitwarden | ESI Client ID, ESI Secret Key, contact e-mail |

---

## A. Before you start (on your PC)

1. Open PowerShell and connect: `ssh tony@167.99.207.145`
2. Have Bitwarden open: you'll be asked for the ESI Client ID and Secret Key.

---

## B. Download the stack (server)

```bash
cd ~
bash <(curl -s https://gitlab.com/allianceauth/allianceauth/-/raw/master/docker/scripts/download.sh)
cd ~/aa-docker
ls
```

You should see `docker-compose.yml`, `.env.example`, a `conf/` folder, `scripts/`, `setup.base.sql`, grafana files.

✅ `ls` shows those files.

## C. Generate the environment file (server)

```bash
./scripts/prepare-env.sh
```

It asks six questions. Answer exactly:

| Prompt | Answer |
|---|---|
| Enter the display name for your auth instance | `The Orlov Family` |
| Enter the base domain | `orlovfamily.space` |
| Enter the subdomain for auth | `auth` |
| Enter an email address (CCP contact) | your e-mail |
| Enter ESI Client ID | paste from Bitwarden |
| Enter ESI Client Secret | paste from Bitwarden (nothing shows? it does show — this prompt isn't hidden) |

The script also generates random passwords for MariaDB, Grafana and the Django secret key and writes them into `.env` and `setup.sql`.

Now one security fix. Docker publishes ports **around** `ufw`, so the proxy manager's admin UI (port 81) would be reachable from the internet. Bind it to localhost only:

```bash
sed -i 's/^PROXY_DASH_PORT=81$/PROXY_DASH_PORT=127.0.0.1:81/' .env
grep -E '^(PROTOCOL|DOMAIN|AUTH_SUBDOMAIN|AA_SITENAME|PROXY_DASH_PORT|AA_DOCKER_TAG|ESI_SSO_CLIENT_ID)=' .env
```

Expected output (your client ID will differ):

```
PROTOCOL=https://
AUTH_SUBDOMAIN=auth
DOMAIN=orlovfamily.space
AA_DOCKER_TAG=registry.gitlab.com/allianceauth/allianceauth/auth:v5.4.0
PROXY_DASH_PORT=127.0.0.1:81
AA_SITENAME="The Orlov Family"
ESI_SSO_CLIENT_ID=<32 hex chars>
```

If anything is wrong, fix it with `nano .env` (Ctrl+O Enter to save, Ctrl+X to exit). **Never** paste `.env` anywhere — it holds every secret of the stack. Back it up to Bitwarden as an attachment/secure note once it's final (end of this runbook).

✅ `grep` output matches the table.

## D. Start the stack (server)

```bash
docker compose --env-file=.env up -d
```

First run downloads ~2 GB of images; 3–8 minutes. When it returns, check:

```bash
docker compose ps
```

Expect ~9 containers, all `Up` / `Up (healthy)` after a minute or two: `auth_mysql`, `redis`, `allianceauth_gunicorn`, `allianceauth_worker_beat`, two `allianceauth_worker`, `allianceauth_worker_services`, `nginx`, `grafana`, `proxy`. (`starting` on the workers is normal for the first 5 minutes.)

If `auth_mysql` keeps restarting, look at `docker compose logs auth_mysql --tail 50`.

## E. Initialise the database and create the admin user (server)

```bash
docker compose exec allianceauth_gunicorn bash
```

The prompt changes to something like `allianceauth@<id>:~/myauth$`. You're now *inside* the auth container. Run:

```bash
auth migrate
auth collectstatic --noinput
auth createsuperuser
```

`createsuperuser` asks for a **username** (use `tony`), e-mail (yours) and a **password** twice (nothing shows while typing). Store this as "AA admin (Django) password" in Bitwarden — it is the break-glass login for `/admin`, separate from EVE SSO.

```bash
exit
```

✅ Back at `tony@ubuntu-...:~/aa-docker$`, no errors from the three `auth` commands.

## F. Configure HTTPS in Nginx Proxy Manager (PC + browser)

The proxy admin UI is only reachable from the server itself (that's the fix from step C), so open a tunnel. **On your PC, in a second PowerShell window:**

```powershell
ssh -L 8181:127.0.0.1:81 tony@167.99.207.145
```

Leave that window open. In your browser go to **http://localhost:8181**.

1. Log in with `admin@example.com` / `changeme`. It immediately forces you to set your name/e-mail and a **new password** → Bitwarden ("NPM admin").
2. Top menu **Hosts → Proxy Hosts → Add Proxy Host**:
   - **Details** tab: Domain Names `auth.orlovfamily.space` · Scheme `http` · Forward Hostname / IP `nginx` · Forward Port `80` · tick **Block Common Exploits** · tick **Websockets Support**.
   - **SSL** tab: SSL Certificate → **Request a new SSL Certificate** · tick **Force SSL** · tick **HTTP/2 Support** · leave HSTS **off** · enter your e-mail · tick "I Agree to the Let's Encrypt Terms".
   - **Save**. It takes ~15 s to obtain the certificate. If it errors, the usual cause is DNS not propagated yet (`nslookup auth.orlovfamily.space` must return `167.99.207.145`) — wait and retry.
3. Grafana: skip for now (not needed; it keeps running internally).

Close the tunnel window when done (Ctrl+C or `exit`).

✅ Proxy host shows a green "Online" badge with a padlock.

## G. First login (browser)

1. Open **https://auth.orlovfamily.space** — you should see the Alliance Auth login page with a "Log in with EVE Online" button and a padlock in the address bar.
2. **Do not click the EVE button yet.** First go to **https://auth.orlovfamily.space/admin/** and log in with the Django superuser (`tony` + the admin password from step E).
3. Now go back to **https://auth.orlovfamily.space/** — you're logged in as the superuser, but with no character. Click **Add Character** (dashboard, top right or under *Character* menu) → EVE SSO opens → log in with the account holding your main → Authorize.
4. Dashboard → **Change Main** → pick your main character → confirm. The dashboard now shows your portrait, corp OARMI, and state `Guest` (states aren't configured yet — Day 2).

This order matters: if you click "Log in with EVE Online" first, AA creates a *second*, non-admin user for your character and you'd have to merge them.

✅ Dashboard shows your main character; `/admin/` opens.

## H. Save the state (server + Bitwarden)

```bash
cd ~/aa-docker
cat .env
```

Copy the whole output into Bitwarden as a secure note / attachment named **"aa-docker .env (prod)"**. If the server ever dies, this file plus a database dump is everything.

Then start a first database backup, so the habit exists from day one:

```bash
mkdir -p ~/backups
docker compose exec -T auth_mysql sh -c 'exec mariadb-dump --all-databases -uroot -p"$MYSQL_ROOT_PASSWORD"' | gzip > ~/backups/aa-$(date +%F).sql.gz
ls -lh ~/backups
```

(A nightly cron for this is set up in Phase 6; for now, run it manually after each configuration day.)

---

## Day 1 completion checklist

- [ ] `docker compose ps` — all containers Up/healthy
- [ ] https://auth.orlovfamily.space loads with a valid certificate (padlock)
- [ ] `/admin/` login works with the Django superuser
- [ ] Your main character is attached to the superuser and set as main
- [ ] `.env` and NPM/Django admin passwords are in Bitwarden
- [ ] First `~/backups/aa-<date>.sql.gz` exists

**Next:** Day 2 — states, auto-groups, groups and the Discord service (`docs/runbooks/02-day-two-membership-and-discord.md`).

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `docker compose up` hangs on "Creating…" | Low entropy on fresh VPS — rare on DO. `sudo apt -y install haveged` then retry. |
| `permission denied while trying to connect to the Docker daemon socket` | You're not in the `docker` group in this session. `exit`, SSH back in. |
| Browser: "502 Bad Gateway" from the proxy | gunicorn still starting or static not collected. Wait 1 min; check `docker compose logs allianceauth_gunicorn --tail 50`. |
| Let's Encrypt fails: "Internal Error" | DNS not propagated, or port 80 not reachable. `nslookup auth.orlovfamily.space` on your PC; `sudo ufw status` on server must list 80 and 443 ALLOW. |
| EVE SSO returns "redirect_uri mismatch" | Callback in the EVE developer app must be exactly `https://auth.orlovfamily.space/sso/callback` (no trailing slash). |
| Page loads but no CSS / looks broken | `auth collectstatic --noinput` wasn't run, or NPM forwards to `allianceauth_gunicorn:8000` instead of `nginx:80`. |
| Need to see what's happening | `docker compose logs -f --tail 100` (Ctrl+C to stop). |
