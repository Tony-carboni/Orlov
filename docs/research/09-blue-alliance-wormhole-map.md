# 09 — Reading a blue alliance's wormhole.systems map, and a C2 entrance board in Discord

Written 2026-10-31. The blue alliance maps its C2 chain on **wormhole.systems** (the hosted instance of the open-source WormholeSystems mapper, Rust + SvelteKit, github.com/WormholeSystems/WormholeSystems). We want two things: our pilots can see the chain, and `#`-something in our Discord always shows the current k-space entrance ("in-hole") of the C2.

## What wormhole.systems offers (verified against its docs and the live OpenAPI spec, 2026-10-31)

**Access.** Access is per map and granted to a character, a corporation or a *whole alliance*, at four levels: Viewer (read systems, connections, signatures; no pilot positions), Member (also live positions, editing the chain, signatures), Manager (also the access list, share links, alerts), Owner. A pilot gets the highest level of any entry that matches them; corp and alliance membership is re-checked hourly. Entries can carry an expiry date. Only entities the site has already seen are searchable in the access UI, so the blue manager may need our alliance's raw EVE id: **99015337** (The Orlov Family), **98843356** (Orlov Arms International).

**Login for our pilots.** EVE SSO at wormhole.systems; scopes are location, ship type, online status, waypoints, publicData. Location tracking is opt-in per map, per character (a toggle on the map), and Viewers never appear.

**API.** The same JSON API the map UI uses, documented at wormhole.systems/api/docs (OpenAPI at /api/openapi.json). Authentication is a session cookie or a **personal access token** (Settings → API tokens; shown once; sent as a Bearer header; acts as the user with the same role). The calls a board needs:
- GET /api/maps/{id} — the full map view: `systems` (each with `is_home`, `name`, `security_status`, `region`, `statics` with destination class, `status`, `kind` system or ghost) and `connections` (`from_system`, `to_system`, `kind` wormhole/stargate, `mass_status` stable/reduced/critical, `time_status` stable/eol/critical/expired, `time_status_updated_at`, `size`, `lifetime_hours`, `created_at`).
- GET /api/maps/{id}/signatures — every signature on the map, so the board can name the exit signature in the home system.
- GET /ws/map/{id} — a WebSocket that sends "something changed" frames (ids only); a client refetches on each frame. Polling the map every few minutes is enough for a board.
- GET /api/maps/{id}?share=TOKEN and GET /api/share/{token} — a **share link** (read-only, Viewer-equivalent) works *without any account*. A Manager generates and can revoke it.

**Discord, built in.** Per map a Manager registers destinations (a plain Discord channel webhook, or the wormhole.systems bot via `/wh alert-channel`) and alerts of three kinds: killmail (kills in the chain), **proximity** (the chain comes within N gate jumps of a named system), jump range (a capital can reach a named system). There is no "post the current chain" or "home static exit" alert, so the entrance board has to be ours.

**Mirroring.** There is no sync between two maps or two instances; export/import moves a map once. Self-hosting exists (four containers, an installer script) but gives us nothing for reading *their* map. **Mirroring in our own mapper is not an option worth pursuing.**

## Options

1. **Ask for alliance access, and nothing else.** The blue manager grants alliance 99015337 Viewer (or Member if we will scout for them). Every Orlov pilot logs in at wormhole.systems and sees the live chain. Zero work on our side. No Discord.
2. **Their alerts into our Discord.** We create a webhook in our channel and hand them the URL; their manager adds it as a destination and sets a *proximity* alert, e.g. "chain within 5 jumps of Raussinen/Piekura", plus a killmail alert if wanted. Event pings only, not a standing board, and every change needs their manager.
3. **Our own entrance board (orlovbot cog).** The bot reads their map through the API and keeps one embed in a channel up to date, like the moon board: home system, the static exit(s) with the k-space system, region and security, jumps to Jita and to our staging, the exit signature id, mass and lifetime state ("EOL since 14:20"), and "no k-space exit mapped" when their scouts have not found the new hole yet. Credential: either a share token from their manager (simplest: no account, revocable at their end) or a personal access token minted by one of our characters that has Viewer access. Both are read-only.
4. **Self-host or mirror.** Rejected: no sync exists; double bookkeeping.

## Proposed path

Do 1 and 3 together, 2 as a cheap extra.

- **Ask the blue alliance for:** alliance-level Viewer access for 99015337 (Member if they want our scouts to edit), the map id (it is in the map URL), and a share token for the bot. If they prefer not to hand out a share token, one of our characters with Viewer access mints a personal access token instead; same result.
- **Build the `entrance` cog** in `deploy/orlovbot/cogs/` next to `moons.py`: settings `ORLOVBOT_WH_MAP_ID`, `ORLOVBOT_WH_SHARE_TOKEN` (or `ORLOVBOT_WH_API_TOKEN`), `ORLOVBOT_WH_CHANNEL_ID`, `ORLOVBOT_WH_STAGING` (our reference system for jump counts). Poll GET /api/maps/{id} every 3 minutes with a descriptive User-Agent, find the system with `is_home`, follow its wormhole connections, classify neighbours as k-space by security class, match them to the home's `statics` (destination class) to tell the static from a wandering hole, pull the signature id from /signatures, and compute jumps with the ESI route endpoint (public). Edit one pinned embed; post a fresh line in the channel only when the exit *changes* (new system, EOL, gone), so the channel doubles as a log.
- **Ask them for one proximity alert** to a webhook in the same channel, so we also get pinged when their chain happens to come near our space.
- Runbook 21 to deploy it (settings in conf/local.py, restart the bot container), handoff entry, and a line in CLAUDE.md.

Jump counts and names come from public ESI; the only non-public data is their map, read with their token, read-only. ESI good practice is unaffected (a route lookup per exit change, cached).
