# deploy/

What differs from the upstream Alliance Auth Docker stack (`aa-docker`, downloaded on Day 1).

| File here | Applied to (on server) | How |
|---|---|---|
| `conf/local.py.append` | `~/aa-docker/conf/local.py` | appended once on Day 2; `corputils` and `discord` lines uncommented with `sed` |
| `env.additions.example` | `~/aa-docker/.env` | real values appended on Day 2 |
| `conf/requirements.txt` | `~/aa-docker/conf/requirements.txt` | extra packages for the custom image (Day 3); `docker-compose.yml` switched from `image:` to `build:` on Day 3 |
| `docker-compose.alliance-site.append` | appended to `~/aa-docker/docker-compose.yml` (services) | the `alliance_site` nginx container serving `~/aa-docker/alliance-site/` for alliance.orlovfamily.space (runbook 15, 2026-10-14) |
| `bin/aa-backup.sh` | `~/bin/aa-backup.sh` | the nightly backup (cron 03:30): database dump, config tarball (`.env`, `conf/`, compose file, `orlovbot/`, `alliance-site/`, `~/bin`, crontab) and the proxy manager's hosts and certificates from the two Docker volumes; 14 days in `~/backups` (runbook 04 A, extended 2026-10-17) |
| `orlovbot/` | `~/aa-docker/orlovbot/` | our own Discord bot modules (`/moons`, moon board, structure board, kill feed, jump freighter watch, juicy killmails, welcome DM, leaderboards, radio, planned fleets board with `/fleet`, the idle moon reminder with `/idlemoons`, the leadership board, the blacklist check with `/blacklist` and its list `blacklist.md`), copied on Day 6 and bind-mounted into every Alliance Auth container; see runbook 08 for the compose and `celery.py` edits that go with it |

Upstream `.env` changes made on Day 1: `PROXY_DASH_PORT=127.0.0.1:81` (proxy-manager admin bound to localhost; reach it via `ssh -L 8181:127.0.0.1:81`).

Server: DigitalOcean Droplet `ubuntu-s-2vcpu-4gb-lon1`, Ubuntu 24.04, user `tony`, stack in `~/aa-docker`, dumps in `~/backups`.
Image: `registry.gitlab.com/allianceauth/allianceauth/auth:v5.4.0`.

**HTTP/2 off on the proxy (2026-11-21).** DigitalOcean's alert on nginx CVE-2026-123007 and CVE-2026-123633 (HTTP/2, fixed in nginx 1.30.7 / 1.31.9): the proxy manager image runs OpenResty on nginx 1.31.1 with no patched image yet (NginxProxyManager issue 6060), so the desktop session switched HTTP/2 off on `auth` and `shipyards` (the other two hosts already had it off): `http2_support=0` in the proxy's SQLite database (hosts 1 and 2, via the container's better-sqlite3), `http2 off;` in `/data/nginx/proxy_host/1.conf` and `2.conf`, `nginx -s reload`; copies of the database and both files in `~/backups/npm-pre-http2off-2026-11-21-0647/`. All four hosts answer HTTP/1.1 only. The two internal `nginx:stable` containers (1.30.5, plain HTTP inside Docker, no HTTP/2) are not reachable from outside. When a proxy manager image on nginx 1.31.9+ exists: backup, pull, recreate the `proxy` container, pull `nginx:stable` 1.30.7+ and recreate `nginx` and `alliance_site`; HTTP/2 may then go back on in the UI (SSL tab) or stay off.
