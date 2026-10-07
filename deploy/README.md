# deploy/

What differs from the upstream Alliance Auth Docker stack (`aa-docker`, downloaded on Day 1).

| File here | Applied to (on server) | How |
|---|---|---|
| `conf/local.py.append` | `~/aa-docker/conf/local.py` | appended once on Day 2; `corputils` and `discord` lines uncommented with `sed` |
| `env.additions.example` | `~/aa-docker/.env` | real values appended on Day 2 |
| `conf/requirements.txt` | `~/aa-docker/conf/requirements.txt` | extra packages for the custom image (Day 3); `docker-compose.yml` switched from `image:` to `build:` on Day 3 |
| `orlovbot/` | `~/aa-docker/orlovbot/` | our own Discord bot modules (`/moons`, moon board, structure board, kill feed, jump freighter watch), copied on Day 6 and bind-mounted into every Alliance Auth container; see runbook 08 for the compose and `celery.py` edits that go with it |

Upstream `.env` changes made on Day 1: `PROXY_DASH_PORT=127.0.0.1:81` (proxy-manager admin bound to localhost; reach it via `ssh -L 8181:127.0.0.1:81`).

Server: DigitalOcean Droplet `ubuntu-s-2vcpu-4gb-lon1`, Ubuntu 24.04, user `tony`, stack in `~/aa-docker`, dumps in `~/backups`.
Image: `registry.gitlab.com/allianceauth/allianceauth/auth:v5.4.0`.
