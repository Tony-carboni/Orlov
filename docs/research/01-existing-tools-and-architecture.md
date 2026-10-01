# Alliance management platform — landscape research & build options

*Research date: 2026-10-01. Target: a platform where alliance members log in with EVE SSO, leadership manages members out of game, and Discord roles are assigned automatically from that data.*

---

## 0. One terminology correction first

**SeAT is not CCP's API.** The in-game data API is **ESI** (EVE Swagger Interface, `esi.evetech.net`), fronted by **EVE SSO** (`login.eveonline.com`) for login and OAuth tokens. **SeAT** is a *third-party, self-hosted PHP/Laravel tool* that consumes ESI and shows you wallets, assets, mail, contracts etc. for the characters/corps that have authorised it.

So the real question is: "which third-party tool (or custom build) sits on top of ESI + SSO and drives Discord?" — and SeAT is one of several candidates, not the foundation.

---

## 1. TL;DR verdict

**Yes — fit-for-purpose freeware exists, and it is Alliance Auth, not SeAT.**

| Need | Alliance Auth (AA) | SeAT | Neucore |
|---|---|---|---|
| Members log in via EVE SSO | ✅ core | ✅ core | ✅ core |
| Main + alt character grouping | ✅ core (main character, states) | ✅ (users with multiple chars) | ✅ (players with chars) |
| Out-of-game member management (who is in, who isn't, kick-list) | ✅ Corp Stats, Member Audit, states/groups | ✅ (corp member lists, roles, titles) | ✅ member tracking, watchlist |
| **Automatic Discord roles from membership** | ✅ **first-party "Discord service"**: AA groups ⇄ Discord roles by name, nick sync, auto-remove on state loss | ⚠️ via `seat-discord-connector` plugin — original repo **archived June 2025**, community fork (`zenobio93`) is on v6.0.x | ✅ via `neucore-discord-plugin` (roles, nicks, kicks) |
| Activity tracking (last login, ship, location) | ✅ Member Audit (`aa-memberaudit`), Corp Stats, AFAT fleet participation | ✅ strong (that's SeAT's whole purpose) | ✅ member tracking (director token) |
| Plugin ecosystem for alliance ops (timers, SRP, fleets, structures, intel) | ✅ very large (`apps.allianceauth.org`) | ✅ good | ⚠️ smaller |
| Maintenance (as of Oct 2026) | ✅ **v5.2.0 released 2026-07-06**, Python 3.12 / Django 5.x, frequent releases | ✅ SeAT 5.0.x, `eveseat/web` 5.0.35 (May 2026), PHP ≥8.1 / Laravel 10 | ✅ **v3.0.1 released 2026-09-29** |
| Install | Docker Compose (official) or bare-metal Ubuntu/CentOS | Docker Compose (official one-liner) | Docker (only supported method since 3.0) |
| License | GPL-2.0 | GPL-2.0 | MIT |

**Recommendation:** run **Alliance Auth** as the member/auth/Discord backbone. Optionally run **SeAT** *alongside* it later if you want deep per-character financial/asset auditing (many alliances run both). Only build custom when there is a specific gap — and then build it as an **AA plugin (Django app)** rather than a from-scratch platform, because AA already solves 90 % of the plumbing (SSO, token refresh, ESI client, Celery workers, Discord bot, permissions).

A from-scratch build is feasible (see §4) but is realistically 2–4 months of part-time work before it reaches parity with what AA gives you on day one, and you'd be re-implementing things the AA community has spent ~9 years hardening.

---

## 2. Candidate tools in detail

### 2.1 Alliance Auth (AA) — **recommended**

- **What it is:** "An auth system for EVE Online to help in-game organizations manage online service access." It automatically grants/revokes access to external services (Discord, Mumble, TeamSpeak 3, SMF…) and to web apps based on the user's *current* in-game membership.
- **Core model:**
  - **States** — mutually exclusive tiers (e.g. `Member`, `Blue`, `Guest`) derived from the user's *main character's* corp / alliance / faction. Evaluated by priority; anyone matching nothing falls into the permanent `Guest` state. Permissions hang off states. *This is exactly the "is this person still in my alliance?" question.*
  - **Groups** — manually-joinable or auto-assigned (auto groups per corp/alliance exist). Groups are what map to Discord roles.
  - **Main character + alts** — every user picks a main; alts are linked under it.
- **Discord service (first-party):** user clicks "Activate Discord" → Discord OAuth2 → AA's bot adds them to the guild, assigns roles whose names match their AA groups, optionally sets their nickname to their main character's name (`DISCORD_SYNC_NAMES`). Periodic Celery tasks (`update_all_groups`, `update_all_nicknames`, `update_all`) re-sync; losing a state removes roles / can kick. Supports "reserved roles" so roles managed by other bots are left alone. Requirements: bot role at the top of the guild hierarchy; bot account has 2FA.
- **Member management / activity apps (community, all pip-installable):**
  - `corpstats` (built in): registered vs *unregistered* members per corp — your "who hasn't authed yet" list. Needs a token with `esi-corporations.read_corporation_membership.v1` from a member of each corp.
  - `aa-memberaudit`: full character audit (skills, assets, wallet, contacts, implants, login history) for vetting/compliance.
  - `allianceauth-afat`: fleet participation (FAT/PAP) tracking via ESI fleets.
  - `allianceauth-discordbot` (`aa-discordbot`): optional second bot with slash commands (`/lookup` member → main/state/groups, timers, sov, price checks, ticketing). Runs *alongside* the core Discord service.
  - Hundreds more at <https://apps.allianceauth.org/>.
- **Stack:** Python 3.12, Django 5.x, Celery + Redis, MariaDB 11.x, gunicorn + nginx. Official **Docker Compose** stack (`aa-docker`: gunicorn, Celery workers/beat, Redis, MariaDB, nginx Proxy Manager, Grafana) — download script at `gitlab.com/allianceauth/allianceauth/-/raw/master/docker/scripts/download.sh`.
- **Extensibility:** plugins are ordinary Django apps; the project's dev docs cover writing services and apps. If we build anything custom, this is where it goes.
- **Maturity:** v5.0.0 (2026-05-08) → v5.2.0 (2026-07-06); large active community (Discord, GitLab).
- **Links:** docs <https://allianceauth.readthedocs.io/> · source <https://gitlab.com/allianceauth/allianceauth> · PyPI <https://pypi.org/project/allianceauth/> · apps <https://apps.allianceauth.org/> · CCP community page <https://developers.eveonline.com/docs/community/alliance-auth/>

### 2.2 SeAT — strong *auditing* tool, weaker as the auth/Discord backbone

- **What it is:** "A simple EVE Online Corporation and API management tool" — wallets, mail, assets, contracts, industry, killmails for characters and corporations. Written in **PHP (≥8.1) / Laravel 10**, MySQL/MariaDB + Redis, Horizon queue workers.
- **Member management:** users (each with N characters), ACL roles, **squads** (SeAT's equivalent of groups, with automatic membership filters), corporation member/role/title views.
- **Discord:** via the plugin family `warlof/seat-connector` + `seat-discord-connector`. The original author's repo was **archived 2025-06-24 (read-only)**. A maintained fork by **zenobio93** exists (`zenobio93/seat-discord-connector`, 6.0.x branch, release v6.0.2 April 2025); it maps Discord roles from six filter types (user, SeAT role, corporation, corp title, alliance, public). It works, but the Discord story is now community-fork-dependent rather than first-party.
- **Install:** official Docker Compose (`eveseat/seat-docker`, one-line bootstrap: `bash <(curl -fsSL https://git.io/get-seat)`), MariaDB + Redis + Traefik.
- **Verdict:** excellent as a *second* tool for deep character/corp auditing; not the best primary auth/Discord system today.
- **Links:** <https://github.com/eveseat/seat> · <https://github.com/eveseat/seat-docker> · docs <https://eveseat.github.io/docs/> · connector fork <https://github.com/zenobio93/seat-discord-connector>

### 2.3 Neucore (Alliance Core Services) — credible alternative

- Built by/for Brave Collective; MIT; PHP backend + Vue frontend; **v3.0.1 released 2026-09-29**; Docker is the only supported deployment since 3.0.
- Features: group management with automation, **ESI proxy/API** (great if we later want to build our own front-end on top), plugin system, **corporation member tracking** (director token), **watchlist** of alliances/corps, MCP server for AI assistants.
- `neucore-discord-plugin`: adds/removes members, maps roles from Neucore groups, nickname patterns (character + corp), kicks on group loss, channel access by group.
- Smaller plugin ecosystem than AA; fewer alliance-ops apps (timers, SRP, fleets).
- **Links:** <https://github.com/tkhamez/neucore> · <https://github.com/tkhamez/neucore-discord-plugin>

### 2.4 Others looked at (not recommended as the primary platform)

| Tool | Notes |
|---|---|
| **ADAPT** | New FastAPI-based "unified Discord + web platform" (doctrines, fleets, timers, mapping, Discord role-based access). **Closed testing, hosted/managed only, not self-hosted, not open source.** Watch, don't depend on. ([forum thread](https://forums.eveonline.com/t/adapt-a-unified-discord-web-platform-for-eve-organization-management-seat-auth-alt-closed-testing/508452)) |
| **Keepstar** (`shibdib/Keepstar`) | Minimal PHP 7 "SSO → Discord role" bot. **Archived Dec 2023.** |
| **EVE Auth bot / Eve Link** | Hosted public Discord auth bots (corp/alliance/coalition roles). Zero hosting, but you don't own the data and they offer no member-management UI. OK as a stop-gap only. |
| **seatplus** | "SeAT with a plus" rewrite; small community. |
| **Hosted AA/SeAT for ISK** | Several forum sellers host AA/SeAT/Pathfinder for ISK. Viable if you don't want to run infra — same software, someone else's server. |

---

## 3. What the platform (whatever we run) *must* deal with — ESI/SSO facts that shape the design

These apply equally to AA, SeAT, Neucore or a custom build, and are the things to verify when configuring whichever we pick.

### 3.1 EVE SSO (OAuth 2.0)
- Endpoints: `https://login.eveonline.com/v2/oauth/authorize/`, `https://login.eveonline.com/v2/oauth/token`, JWKS `https://login.eveonline.com/oauth/jwks`, metadata `https://login.eveonline.com/.well-known/oauth-authorization-server`. The old `/oauth/authorize|token|verify` v1 endpoints are deprecated.
- Server-side web apps use the **authorization-code flow with client secret** (HTTP Basic `client_id:secret` on the token call); SPAs/native apps use **PKCE**.
- Authorization code lifetime **5 min**; **access token (JWT) lifetime 20 min**; refresh tokens are long-lived but **may rotate on refresh** — always store the returned refresh token.
- JWT validation: verify signature via JWKS (RS256, ES256 "coming"), `iss` ∈ {`login.eveonline.com`, `https://login.eveonline.com`}, `aud` contains your `client_id` **and** `"EVE Online"`, `exp`. Useful claims: `sub` = `CHARACTER:EVE:<id>`, `name`, **`owner`** (changes if the character is transferred to another account — the standard "re-auth required" signal), `scp` (scopes).
- Register the app at the EVE Developers portal (<https://developers.eveonline.com/>); one client ID/secret per environment; callback URL must match exactly.

### 3.2 ESI
- **Versioning changed:** new routes no longer carry `/v1/` etc. in the path. Send an **`X-Compatibility-Date: YYYY-MM-DD`** header (or `compatibility_date` query param) on every call; CCP promises ≥1 year backwards compatibility per date. Legacy routes were pruned 2026-03-24 (`/status.json` → `/meta/status`). Any library we use must support this (AA's `django-esi` and SeAT's `eseye` do).
- Endpoints relevant to member management and the scope/role each needs:

| Endpoint | Scope | In-game role on the token's character | Returns |
|---|---|---|---|
| `GET /corporations/{id}/members/` | `esi-corporations.read_corporation_membership.v1` | any member | list of character IDs |
| `GET /corporations/{id}/membertracking/` | `esi-corporations.track_members.v1` | **Director** | per member: `logon_date`, `logoff_date`, `start_date`, `ship_type_id`, `location_id`, `base_id` |
| `GET /corporations/{id}/roles/` | `esi-corporations.read_corporation_roles.v1` | Personnel Manager (or grantable) | roles per member |
| `GET /corporations/{id}/titles/`, `/members/titles/` | `esi-corporations.read_titles.v1` | **Director** | titles |
| `POST /characters/affiliation/` | none (public) | — | character → corp → alliance (bulk, 1 000 IDs) |
| `GET /alliances/{id}/corporations/` | none (public) | — | member corps of the alliance |
| `GET /characters/{id}/online/` | `esi-location.read_online.v1` | self | online now / last login/logout |
| `GET /characters/{id}/fleet/` | `esi-fleets.read_fleet.v1` | self | fleet membership (for FAT/PAP) |

- Cache time on the corp endpoints is 1 h — polling faster is pointless.

### 3.3 The structural constraint for an *alliance* leader
An alliance executor has **no ESI superpowers over member corporations**. Per-corp data (member list, last-login tracking, titles) requires a token from a character **inside that corp** with the right in-game role (Director for member tracking). Practically:
- Public data (affiliation, alliance → corp list) tells you *who is in the alliance* for free, which is enough for **"is this Discord user a current alliance member?" → roles**.
- *Activity* data (last login, ship, location) requires **each member-corp CEO/Director to add a token** to the platform. Every tool above (AA Corp Stats/Member Audit, SeAT corporation tokens, Neucore member tracking) is built around collecting these director tokens corp by corp. Plan an onboarding step for corp leadership.
- Alternatively, require every *member* to add their own characters with `esi-location.read_online.v1` etc. (AA Member Audit approach) — more intrusive, but works without directors.

### 3.4 Discord side
- A **bot** (token) in the guild with `Manage Roles`, `Manage Nicknames`, `Kick Members`, and `Create Instant Invite`; the bot's own role must sit **above** every role it manages. Role assignment via `PUT/DELETE /guilds/{guild}/members/{user}/roles/{role}`; add-to-guild via OAuth2 `guilds.join` + `PUT /guilds/{guild}/members/{user}`.
- **User linking** via Discord OAuth2 (`identify` scope, optionally `guilds.join`) so we store `discord_user_id ↔ EVE user`.
- Optional modern alternative/complement: **Linked Roles** (`role_connections.write` + application role-connection metadata) lets Discord itself gate a role on metadata we publish ("is_member = true", "corp = X"). Nice, but it's per-role opt-in by the user and doesn't *remove* people; the bot-driven sync remains necessary.
- Privileged intents (`GUILD_MEMBERS`) are needed if the bot wants to react to join events rather than poll.

---

## 4. If we build it ourselves anyway — minimum viable architecture

Only worth it if we want a radically different UX or a stack we're committed to (e.g. TypeScript). Components:

1. **Web app + API** (e.g. Next.js/NestJS, FastAPI, or Django): EVE SSO login (auth-code flow, server-side), session, "my characters" page, admin pages.
2. **Identity model:** `User` → `Character[]` (one main), each character with `owner_hash`, corp, alliance, last-affiliation-check; `DiscordAccount` 1:1 with User; `EsiToken` per character/scope-set (encrypted refresh token, rotate-on-refresh).
3. **Membership engine:** nightly/hourly job → `POST /characters/affiliation/` for all known characters → recompute each user's *state* (Member / Blue / Guest) from main character's alliance/corp vs. configured lists; record transitions (joined/left) as events.
4. **Director-token ingestors:** per corp, pull `/members/`, `/membertracking/`, `/roles/`, `/titles/` hourly; store `last_logon`, `ship`, `location`; flag inactive > N days; flag members not registered in the platform.
5. **Discord sync worker:** reconcile desired roles (from state + groups + corp + titles mapping table) vs. actual guild roles; set nickname pattern `[CORP] Character`; remove roles / kick on Guest; respect a "managed roles" allow-list so other bots' roles are untouched. Idempotent, rate-limit aware (Discord global 50 req/s, per-route buckets).
6. **Job queue + scheduler** (Celery/BullMQ/Temporal) and **Postgres/MariaDB + Redis**.
7. **Ops:** Docker Compose, HTTPS (Caddy/Traefik), secrets for SSO client secret + Discord bot token, backups of the token table (losing it means every member re-auths).

Effort estimate for a solo part-time builder to reach "SSO login + state engine + Discord role sync + director activity tracking + basic admin UI": roughly **8–16 weeks**. Alliance Auth gives that on day one; custom work is better spent on an AA plugin for whatever is genuinely missing.

---

## 5. Suggested next steps

1. **Stand up Alliance Auth via Docker Compose** on a small VPS (2 vCPU / 4 GB is plenty for a young alliance) with HTTPS.
2. Register an EVE developer application (callback → AA) and a Discord application/bot; configure the AA **Discord service**; create the Member/Blue/Guest **states** for the alliance and friendly entities.
3. Install `corpstats` (built in) and `aa-memberaudit`; have each member-corp CEO/director add a token so activity tracking lights up alliance-wide.
4. Add `aa-discordbot` for in-Discord `/lookup` and ticketing; `allianceauth-afat` for fleet participation if that matters for your activity policy.
5. Keep a list of real gaps for 2–4 weeks of use; build an AA plugin for those (this repo can host it) instead of a parallel platform.
6. Re-evaluate SeAT alongside AA only if the leadership needs wallet/asset-level auditing.

---

## Sources

- CCP: [EVE SSO docs](https://developers.eveonline.com/docs/services/sso/) · [ESI versioning / X-Compatibility-Date](https://developers.eveonline.com/blog/changing-versions-v42-was-getting-out-of-hand) · [Spring cleaning: legacy routes removed 24 Mar 2026](https://developers.eveonline.com/blog/spring-cleaning-legacy-routes-removed-24-march-2026) · [Removal of v1 auth tokens](https://developers.eveonline.com/blog/removal-of-v1-authentication-tokens) · [SSO endpoint deprecations](https://developers.eveonline.com/blog/sso-endpoint-deprecations-2) · [Community tools index](https://developers.eveonline.com/docs/community/)
- esi-docs: [Web-based SSO flow](https://github.com/esi/esi-docs/blob/master/docs/sso/web_based_sso_flow.md) · [Validating EVE JWTs](https://github.com/esi/esi-docs/blob/master/docs/sso/validating_eve_jwt.md) · [Refreshing access tokens](https://docs.esi.evetech.net/docs/sso/refreshing_access_tokens.html)
- Alliance Auth: [docs](https://allianceauth.readthedocs.io/) · [Discord service](https://gitlab.com/allianceauth/allianceauth/-/blob/master/docs/features/services/discord.md) · [States](https://gitlab.com/allianceauth/allianceauth/-/blob/master/docs/features/core/states.md) · [Corp Stats](https://gitlab.com/allianceauth/allianceauth/-/blob/master/docs/features/apps/corpstats.md) · [Docker install](https://allianceauth.readthedocs.io/en/latest/installation-containerized/docker.html) · [v5.2.0 release](https://newreleases.io/project/gitlab/allianceauth/allianceauth/release/v5.2.0) · [aa-memberaudit](https://pypi.org/project/aa-memberaudit/) · [allianceauth-afat](https://pypi.org/project/allianceauth-afat/) · [aa-discordbot](https://github.com/pvyParts/allianceauth-discordbot) · [apps catalogue](https://apps.allianceauth.org/)
- SeAT: [eveseat/seat](https://github.com/eveseat/seat) · [composer.json](https://github.com/eveseat/seat/blob/master/composer.json) · [seat-docker](https://github.com/eveseat/seat-docker) · [eveseat/web releases](https://github.com/eveseat/web/releases) · [warlof/seat-discord-connector (archived)](https://github.com/warlof/seat-discord-connector) · [zenobio93 fork](https://github.com/zenobio93/seat-discord-connector) · [CCP SeAT page](https://developers.eveonline.com/docs/community/seat/)
- Neucore: [tkhamez/neucore](https://github.com/tkhamez/neucore) · [CHANGELOG](https://github.com/tkhamez/neucore/blob/main/CHANGELOG.md) · [neucore-discord-plugin](https://github.com/tkhamez/neucore-discord-plugin)
- Others: [ADAPT forum thread](https://forums.eveonline.com/t/adapt-a-unified-discord-web-platform-for-eve-organization-management-seat-auth-alt-closed-testing/508452) · [Keepstar](https://github.com/shibdib/Keepstar) · [EVE Auth Discord bot](https://forums.eveonline.com/t/eve-auth-discord-bot/86440) · [Eve Link](https://forums.eveonline.com/t/simplified-esi-auth-for-discord-eve-link/421714) · [seatplus](https://seatplus.net/) · [awesome-eve list](https://github.com/devfleet/awesome-eve)
- Discord: [Linked Roles / role connection metadata](https://docs.discord.com/developers/resources/application-role-connection-metadata) · [Configuring app metadata for linked roles](https://docs.discord.com/developers/tutorials/configuring-app-metadata-for-linked-roles)
- goesi (ESI field/role reference): [CorporationApi.md](https://github.com/antihax/goesi/blob/master/esi/docs/CorporationApi.md) · [membertracking model](https://github.com/antihax/goesi/blob/master/esi/docs/GetCorporationsCorporationIdMembertracking200Ok.md)
