# Runbook 11 — the kill feed: kills and losses in `#zkillboard`

*Prerequisite: runbook 08 (the bot container `allianceauth_discordbot` is running).*
*Time: ~10 min. You do section A (Discord). Sections B and C are run by Claude in the **local session**.*

**Goal:** every time a pilot of The Orlov Family kills a ship or loses one, the bot posts one message in `#zkillboard`: green for a kill, red for a loss, with the ship, the victim, who got the final blow, our own pilots on the kill, the system, the ISK value and the time. The title links to the killmail on zKillboard.

How it works:
- Every **5 minutes** the bot asks zKillboard for the alliance's latest killmails and posts the ones it has not posted yet, oldest first.
- A kill shows up **up to an hour after zKillboard has it** (found 2026-10-10: zKillboard's API answers are cached by Cloudflare for one hour, `cache-control: max-age=3600`; the server keeps getting the copy it was first served until that hour is up, so a fight at 13:23 posted only after 14:19). Within that limit it is as fast as zKillboard, but zKillboard only learns of a killmail when one of the pilots involved (or their corp) is linked to zKillboard, or when somebody posts it there by hand. A killmail that reaches zKillboard up to **3 days** late is still posted; older ones are skipped.
- The feed never pings. It posts at most 10 killmails per check; the rest follows 5 minutes later.
- What was posted is remembered outside the bot (in the cache), so restarting the bot or the server neither repeats nor floods. On its very first run the bot marks everything that already exists as known and posts nothing.
- A loss caused by one of our own pilots is posted as a loss with a line "Friendly fire by".
- Only the alliance is followed. Corps outside the alliance (the structure holding corp, a corp that has not joined yet) are not, unless their ID is added to the setting below.

Considered and not used: the Alliance Auth app `aa-killtracker` (a full tracker with its own database tables, webhooks and an image rebuild; more than a simple feed needs) and zKillboard's live streams (faster by a few minutes, but a permanently open connection to keep alive).

## Known values

| Item | Value |
|---|---|
| Channel | `#zkillboard` in the `bots` category (the bot finds it by **name**) |
| Settings | `ORLOVBOT_KILLFEED_CHANNEL`, `ORLOVBOT_KILLFEED_ALLIANCE_IDS` (`99015337`, The Orlov Family), `ORLOVBOT_KILLFEED_CORPORATION_IDS` (empty) in `conf/local.py`; block "Kill feed" at the end of `deploy/conf/local.py.append` |
| Code | `deploy/orlovbot/cogs/killfeed.py` → `~/aa-docker/orlovbot/cogs/killfeed.py`, registered in `orlovbot/auth_hooks.py` |
| Source | `https://zkillboard.com/api/allianceID/99015337/` (public, no login) |
| Check interval | 5 minutes (`CHECK_MINUTES` in `killfeed.py`) |

---

## A. Create the channel (Discord, 3 min)

1. In the `bots` category: **Create Channel** → Text → name `zkillboard` (exactly this).
2. Channel → **Edit Channel → Permissions**: whoever should read it gets View Channel ✅ and Send Messages ❌; the bot's role `Orlov auth` needs View Channel ✅, Send Messages ✅, Embed Links ✅.
3. **Save Changes**.

✅ Done when the channel exists and the bot may post. *Done 2026-10-05 by the owner.*

## B. Switch the feed on (server — local session)

*Done 2026-10-05 15:39 UTC.* Steps, for reference:

1. Copy `deploy/orlovbot/` to `~/aa-docker/orlovbot/` (Unix line endings); keep a copy of the old folder in `~/backups`.
2. Append the "Kill feed" block from `deploy/conf/local.py.append` to `conf/local.py` with `>>`.
3. Dry run in a fresh process in the bot container: import the module, read zKillboard, build the message for the newest killmail, run the logic checks. Nothing is posted.
4. Restart **only** the bot: `docker compose restart allianceauth_discordbot`.

✅ Done when the bot's output lists `orlovbot.cogs.killfeed` under "Cogs Loaded" and says "Kill feed: first run, N existing killmails count as already posted".

## C. Check (Discord)

- The local session can queue one **test post**: the bot posts the newest existing killmail once more, marked "Test post" at the bottom. Done once on 2026-10-05 (the capsule loss of 3 October).
- The real proof is the next kill or loss: it should appear within about 10 minutes of showing up on zKillboard.

## Changing things later

| Wish | How |
|---|---|
| Also follow a corp outside the alliance | add its corporation ID to `ORLOVBOT_KILLFEED_CORPORATION_IDS` in `conf/local.py` and in `deploy/`, restart the bot |
| Another channel | rename the channel, or change `ORLOVBOT_KILLFEED_CHANNEL`, restart the bot |
| Switch the feed off | `ORLOVBOT_KILLFEED_CHANNEL = ""`, restart the bot |
| Check more or less often | `CHECK_MINUTES` in `killfeed.py` (zKillboard asks clients not to hammer it; 5 minutes is polite) |
| Skip cheap killmails (capsules, shuttles) | not built; ask the local session for a minimum value |

## Completion checklist

- [x] `#zkillboard` exists (A)
- [x] Feed switched on, bot output clean, test post sent (B, C)
- [ ] Owner confirms the test post looks right
- [ ] First real kill or loss appeared by itself

## Troubleshooting
- **A kill is on zKillboard but not in the channel, and the bot log shows nothing** → most likely the one-hour cache. Check from the server with curl: a `cf-cache-status: HIT` with an `age` in the hundreds or thousands and a `last-modified` before the kill means the list the bot sees is stale; it refreshes at the `expires` time (`last-modified` + 1 h) and the bot posts at its first 5-minute check after that, 10 per check. Your PC may see the kill earlier because it talks to a different Cloudflare edge with its own copy. Nothing to fix on the server; the alternatives are in the handoff of 2026-10-10.

- **A kill is on zKillboard but not in the channel** → wait two checks (10 minutes). Then the local session reads `docker compose logs --tail 50 allianceauth_discordbot`: "zKillboard gave no answer" means zKillboard was down or slow and the bot retries by itself; "could not be posted" with "Missing Permissions" means the `Orlov auth` role lacks a permission from A2.
- **A kill is not on zKillboard at all** → nobody involved is linked to zKillboard. Log in once on zkillboard.com with the character (or have the corp CEO add the corp there), or post the killmail by hand; the feed picks it up if that happens within 3 days.
- **Names show as "unknown"** → EVE's API did not answer when the post was made; the link in the title still leads to the full killmail.
- **The same killmail twice** → should be impossible (it is recorded before it is posted); if it happens, tell the local session.
