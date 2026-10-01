# Foundation choice and step plan

*Companion to `01-existing-tools-and-architecture.md`. Written for someone who has not run any of these tools before.*

---

## 1. Can we freely use them?

| Tool | License | Cost | What the license means for us |
|---|---|---|---|
| **Alliance Auth** | GPL-2.0 | Free | Run it, modify it, host it for your alliance — no obligations. GPL only kicks in if you *distribute* a modified AA to others; then you must share the source. Plugins we write and keep private: no obligation. If we publish them, they should be GPL-compatible (most community AA apps are GPL or MIT). |
| **SeAT** | GPL-2.0 | Free | Same as above. |
| **Neucore** | MIT | Free | Do anything, keep the copyright notice. |
| EVE SSO / ESI | CCP developer licence | Free | Register an app on the dev portal; agree to the licence (no selling of data, respect rate limits/cache timers, one app per purpose). |
| Discord bot/API | Discord developer ToS | Free | Verification is only required above 100 guilds — irrelevant here. |

Hosting is the only real cost: one small VPS (2 vCPU / 4 GB RAM / 40 GB disk — ~€4/month at Hetzner, ~$24/month at DigitalOcean for the same size) plus a domain (~€10/year). Everything else is free.

---

## 2. Proposed combination

**Backbone: Alliance Auth. Nothing else on day one.**

Why only AA: it is the one tool that covers all three requirements first-party (SSO → member states → Discord roles), it is the most actively maintained, and its plugin catalogue means most things you will want next already exist. Adding SeAT or Neucore at the same time would mean three login systems and three Discord bots for your members to understand.

| Layer | Component | Role |
|---|---|---|
| Core | **Alliance Auth 5.x** (Docker Compose stack: gunicorn, Celery workers + beat, Redis, MariaDB, Nginx Proxy Manager, Grafana) | SSO login, main/alt characters, states, groups, permissions, admin UI |
| Discord | **AA Discord service** (built in) | Links Discord accounts, assigns roles from groups, nick sync, auto-removal |
| Discord (optional, phase 4) | **`allianceauth-discordbot`** | `/lookup`, `/auth`, ticketing, reminders — in-Discord convenience for leadership |
| Member mgmt | **`corpstats`** (built in) | Who in each corp is / isn't registered |
| Member mgmt | **`aa-memberaudit`** | Per-character audit: login history, skills, assets, wallet, contacts; compliance reports |
| Activity | **`allianceauth-afat`** | Fleet participation (PAP) tracking — if activity is measured by fleet attendance |
| Later, as needed | `aa-structures`, `aa-timerboard`/`aa-opcalendar`, `aa-srp`, `aa-fleetfinder`, `aa-killtracker` | Structure fuel/timers, ops calendar, SRP, killboard feeds |
| Later, optional | **SeAT** alongside AA | Only if leadership wants wallet/asset-level auditing across corps |
| Custom (phase 6) | **Our own AA plugin(s)** in this repo | Alliance-specific policy that nothing covers (e.g. custom activity scoring → auto group) |

Neucore: not part of the plan. It overlaps almost entirely with AA and has a smaller ecosystem; the only thing it does notably better (ESI proxy for external apps) we can revisit if we ever build separate apps.

---

## 3. What lives in this repository

```
Orlov/
├── docs/
│   ├── research/           # these documents
│   └── runbooks/           # how-to: deploy, upgrade, backup, onboarding a corp director
├── deploy/
│   ├── docker-compose.yml  # from aa-docker, with our overrides
│   ├── .env.example        # placeholders only — real secrets never committed
│   └── conf/local.py       # AA settings (states, Discord, plugins) — secrets via env vars
└── plugins/                # phase 6: our own AA apps (Django packages)
```

Secrets (SSO client secret, Discord bot token, DB passwords) stay in `.env` on the server, never in git.

---

## 4. Step plan

Each phase ends with a checkable outcome. Phases 0–3 get you a working auth + Discord system; that is the minimum before inviting members.

### Phase 0 — Prerequisites (an afternoon)
1. **VPS**: Ubuntu 24.04 LTS, 2 vCPU / 4 GB / 40 GB SSD (Hetzner ~€4/mo; DigitalOcean ~$24/mo for the same). Create a non-root sudo user; enable `ufw` allowing 22/80/443.
2. **Domain**: buy one; create an `A` record `auth.<domain>` → VPS IP.
3. **Install Docker** (Docker's official `apt` repo, includes `docker compose`), plus `git` and `curl`.
4. **EVE Developer application** at <https://developers.eveonline.com/>: name it after the alliance; callback URL `https://auth.<domain>/sso/callback`; scopes: start with `publicData` plus the scopes `aa-memberaudit` lists (we can add more later). Save **Client ID** and **Secret Key**.
5. **Discord application** at <https://discord.com/developers/applications>: create app → add Bot → copy **Bot Token**; OAuth2 → add redirect `https://auth.<domain>/discord/callback`; copy **Client ID / Secret**; enable *Server Members Intent*. Note your **Guild (server) ID** (Discord → User Settings → Advanced → Developer Mode → right-click server → Copy ID).
6. **Dedicated EVE character for the system?** Not required. You will log in with your own main as the first superuser.
7. **Decide the state model** on paper before touching settings:
   - `Family Member` — main character in the alliance.
   - `Family Friend` — allied alliances/corps (standings holders).
   - `Guest` — everyone else (built in, cannot be removed).
   Discord roles (decided 2026-10-01): `Alliance Director`, `Corp Director`, `FC`, `Family Member`, `Family Friend`, `corp_<TICKER>` per corp.

**Outcome:** VPS reachable, DNS resolves, both developer apps created, state/role design written down.

### Phase 1 — Deploy Alliance Auth (1–2 hours)
1. On the VPS: `bash <(curl -s https://gitlab.com/allianceauth/allianceauth/-/raw/master/docker/scripts/download.sh)` → creates `aa-docker/`.
2. `./scripts/prepare-env.sh` → generates `.env` with random DB/Redis passwords and a Django secret.
3. Edit `.env`: `AA_SITENAME`, `DOMAIN=auth.<domain>`, `PROTOCOL=https://`, `ESI_SSO_CLIENT_ID`, `ESI_SSO_CLIENT_SECRET`, `ESI_USER_CONTACT_EMAIL`.
4. `docker compose --env-file=.env up -d`.
5. Nginx Proxy Manager (port 81 initially): add proxy host `auth.<domain>` → `allianceauth_gunicorn:8000`, request a Let's Encrypt cert, force SSL. Then close port 81 externally.
6. `docker compose exec allianceauth_gunicorn bash` → `auth migrate`, `auth collectstatic`, `auth createsuperuser` (username + password; you'll attach your EVE character after first SSO login).
7. Open `https://auth.<domain>` → log in with EVE SSO using your main → in Django admin (`/admin`) tie that character to the superuser.
8. Commit the sanitized `docker-compose.yml`, `.env.example` and `conf/local.py` into `deploy/` in this repo.

**Outcome:** you can log in to AA with your EVE character over HTTPS; admin works.

### Phase 2 — Configure membership (1 hour)
1. **Admin → States**: create `Family Member` (priority 100) with your alliance (today: corp OARMI) in *member corporations/alliances*; create `Family Friend` (priority 50) with allied entities. Leave `Guest`. AA syncs the state name itself as a Discord role.
2. **Admin → Auto Groups** (`allianceauth.eveonline.autogroups`): enable *corp groups* with prefix `corp_` and name source *ticker* so every member automatically lands in `corp_<TICKER>` (e.g. `corp_OARMI`). Leave alliance groups off (the state already covers it).
3. **Groups**: create `Alliance Director` (hidden), `Corp Director` (hidden), `FC` (request + approval).
4. **Permissions**: assign to the `Member` state what every member may use; give leadership groups the extra permissions (e.g. `corpstats.view_corp_corpstats`).
5. Test with a second account/alt from another corp to confirm `Guest` behaviour.

**Outcome:** logging in with an alliance main yields `Member` + auto groups; an outsider yields `Guest` and sees nothing.

### Phase 3 — Discord integration (1 hour)
1. In `conf/local.py` add `'allianceauth.services.modules.discord'` to `INSTALLED_APPS`; set `DISCORD_GUILD_ID`, `DISCORD_CALLBACK_URL`, `DISCORD_APP_ID`, `DISCORD_APP_SECRET`, `DISCORD_BOT_TOKEN`, `DISCORD_SYNC_NAMES = True`; add the Discord Celery beat entries from the AA docs. Restart the stack, run `auth migrate`.
2. **Services** page in AA → "Link Discord Server" → invites the bot to your guild with the right permissions. In Discord, drag the bot's role to the **top** of the role list.
3. Discord roles already exist with **exactly the same names** as the AA states/groups (`Family Member`, `Family Friend`, `corp_OARMI`, `FC`, `Alliance Director`, `Corp Director`). Mark roles belonging to other bots (e.g. music bots) as *reserved* in AA so they are left alone.
4. Give the `discord.access_discord` permission to the `Family Member` and `Family Friend` states.
5. Test: as a member, Services → Discord → Activate → you are added to the server with the right roles and nickname. Remove yourself from a group → within the beat interval the role disappears.

**Outcome:** Discord roles are driven entirely by AA; nobody needs manual role assignment anymore.

### Phase 4 — Member tracking (2–3 hours, plus waiting on corp directors)
1. `pip install aa-memberaudit allianceauth-afat allianceauth-discordbot` inside the container (or, better, in a custom image as the AA docs recommend); add to `INSTALLED_APPS`; migrate; add their beat schedules.
2. **Corp Stats** (built in): each corp's CEO/director logs into AA and clicks *Add Corp Stats* — this stores a token with `esi-corporations.read_corporation_membership.v1`. You now see registered vs. unregistered members per corp.
3. **Member Audit**: set compliance policy ("every member must register all characters"); members add characters; leadership sees login dates, skills, assets. Enable the compliance group so non-compliant members automatically lose a group (and therefore a Discord role).
4. **AFAT**: FCs create FAT links from ESI fleet; participation is logged automatically.
5. **aa-discordbot**: run as an extra container (`allianceauth_discordbot`); verify `/lookup <character>` works.

**Outcome:** you can answer "who is inactive", "who hasn't registered", "who attended fleets" from one place.

### Phase 5 — Roll out to members (ongoing)
1. Write a one-page member guide: log in, add all characters, activate Discord. Pin it in Discord.
2. Switch Discord to **auth-gated**: unverified users see only a `#how-to-auth` channel; everything else requires the `Family Member` role.
3. Ask each corp CEO to add Corp Stats + Member Audit tokens (runbook in `docs/runbooks/`).
4. Set a compliance date; after it, Member Audit's compliance group handles stragglers.

### Phase 6 — Operate and extend (ongoing)
1. **Backups**: nightly `mariadb-dump` of the AA database + `.env` to off-box storage. Losing the token table means every member re-authenticates.
2. **Updates**: `docker compose pull` / rebuild the custom image monthly; read the AA changelog first. Test on a staging copy if the alliance is large.
3. **Monitoring**: the stack ships Grafana; watch Celery queue length and ESI error counts.
4. **Gaps → custom plugin**: after 2–4 weeks keep a list of "I wish it could…". Build those as an AA app in `plugins/` (Django app, uses `django-esi` for tokens, Celery tasks for sync, AA's permission system). Example first plugin: an alliance activity score (fleet PAPs + login recency) that auto-assigns an `Active` group → Discord role.

---

## 5. Timeline summary

| Phase | Effort | Blocked on |
|---|---|---|
| 0 Prerequisites | half a day | VPS/domain purchase |
| 1 Deploy AA | 1–2 h | — |
| 2 Membership config | 1 h | state design |
| 3 Discord | 1 h | — |
| 4 Tracking apps | 2–3 h + waiting | corp directors adding tokens |
| 5 Rollout | 1–2 weeks | members |
| 6 Operate/extend | continuous | real-world gaps |

Working auth + Discord in roughly **one weekend**; full member-tracking picture once directors have added tokens.
