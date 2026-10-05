# Runbook 09 — the moon board: an always-current list in Discord

*Prerequisite: runbook 08 sections A–C (the bot container `allianceauth_discordbot` is running).*
*Time: ~10 min. You do section A (Discord, 3 min). Sections B and C are run by Claude in the **local session** (say "run runbook 09 section B").*

**Goal:** a channel `#moon-board` that always shows one message, "Upcoming moon extractions", with every running extraction of our own moons: structure, moon, a live countdown, the EVE time and the arrival time in each reader's own time zone. Nobody has to ask or ping; the bot keeps the message current.

How it works:
- The bot posts **one** message in `#moon-board` and from then on **edits that same message**. It never posts a second one, so the channel stays a single tile.
- The countdown ("in 5 days", "in 3 hours") is drawn live by Discord on each member's screen. The bot does not need to edit the message for it to tick.
- Every 10 minutes the bot compares the board with Moon Mining and rewrites it with whatever changed: a new extraction, a cancelled one, a chunk that arrived, a field that was fractured.
- The last entry of the board is **Last checked**, with a live "x minutes ago" and the time in your own time zone. The bot refreshes it at every check, so it should never be much older than 10 minutes; if it is, the bot is not running (added 2026-10-05).
- Editing a message does not notify anyone, and there are no moon pings any more: on 2026-10-05 the owner dropped the Day 5 reminders and removed `#moon-timers`. The board is the only place moon times are announced.
- It reads our own extractions only (the corps registered under Moon Mining → Add Owner). No public timers.
- `/moons` from runbook 08 keeps working and shows the same list on request.

## Known values

| Item | Value |
|---|---|
| Channel | `#moon-board` (the bot finds it by **name**) |
| Setting | `ORLOVBOT_MOON_BOARD_CHANNEL = "moon-board"` in `conf/local.py` (block "Moon board" at the end of `deploy/conf/local.py.append`) |
| Code | `deploy/orlovbot/cogs/moons.py` → `~/aa-docker/orlovbot/cogs/moons.py` |
| Check interval | 10 minutes (`CHECK_MINUTES` in `deploy/orlovbot/board.py`, shared with the structure board of runbook 10) |
| Bot output | `docker compose logs allianceauth_discordbot` (the same block switches on the bot's log lines) |

---

## A. Create the channel (Discord, 3 min)

1. Right-click the `ALLIANCE` category → **Create Channel** → Text → name `moon-board` (exactly this, lower case with the dash).
2. Channel → **Edit Channel → Permissions**:
   - `@everyone`: View Channel ❌
   - `Family Friend`: View Channel ❌
   - `Family Member`: View Channel ✅, Send Messages ❌
   - the **bot's role**, `Orlov auth`: View Channel ✅, Send Messages ✅, Embed Links ✅, Read Message History ✅
3. **Save Changes**.

✅ Done when `#moon-board` exists, members can read but not write, and the bot's role is allowed to post. Within 10 minutes of the bot running with the board switched on, the board message appears by itself.

## B. Switch the board on (server — local session)

*Done 2026-10-05 11:27 UTC by the local session. The bot's output shows it logged in, loaded `aadiscordbot.cogs.about`, `aadiscordbot.cogs.time` and `orlovbot.cogs.moons`, and then "no text channel named #moon-board yet": it is waiting for section A.*

The local session does this, announcing each change first:

1. Copy `deploy/orlovbot/cogs/moons.py` from the repo to `~/aa-docker/orlovbot/cogs/moons.py` (Unix line endings).
2. Append the "Moon board" block from `deploy/conf/local.py.append` to `conf/local.py` with `>>`.
3. `manage.py check` and an import of `orlovbot.cogs.moons` in a fresh process, to catch a typo before the bot restarts.
4. Restart **only** the bot: `docker compose restart allianceauth_discordbot`. No rebuild, and auth itself is not interrupted. The other containers pick the new setting up at their next restart; they do not use it.

✅ Done when the bot's output shows it logged in, loaded `orlovbot.cogs.moons`, and either "Upcoming moon extractions: board posted in #moon-board" ("found the board message" on later restarts) or, if section A is not done yet, "no text channel named #moon-board yet".

The channel may be moved to another category at any time: the bot finds it by name. Keep the name and the four permissions of the `Orlov auth` role.

## C. Check (Discord)

- `#moon-board` shows one message titled "Upcoming moon extractions" with Orlov Mining Facility I and a countdown.
- After the next change in Moon Mining (for example when the chunk arrives on Sat 10 Oct 17:01 EVE time) the same message reads "Chunk has arrived, field can be fractured" within 10 minutes.

## Changing things later

| Wish | How |
|---|---|
| Another channel | Rename the channel, or change `ORLOVBOT_MOON_BOARD_CHANNEL` in `conf/local.py` and in `deploy/`, then restart the bot |
| Switch the board off | Set `ORLOVBOT_MOON_BOARD_CHANNEL = ""`, restart the bot, delete the message by hand |
| Board message deleted by accident | Nothing to do: the bot posts a new one at its next check |
| More than 10 extractions | Raise `MAX_ROWS` in `moons.py` (Discord allows 25 entries per message) |

## Completion checklist

- [x] `#moon-board` created with the permissions above (A) — bot output 2026-10-05 11:30 UTC: "Moon board posted in #moon-board"
- [x] Board switched on, bot restarted, no errors in its output (B)
- [ ] Board message visible and correct (C)

## Troubleshooting

- **No message after 10 minutes** → the local session reads `docker compose logs --tail 50 allianceauth_discordbot`. "no text channel named" means the name differs (check spelling, lower case). "Missing Permissions" or "Missing Access" means the bot's role lacks one of the four permissions in A2.
- **Two board messages** → someone renamed the channel and back, or the bot could not read the history. Delete the older one by hand; the bot keeps using the one it finds first (the newest).
- **Board shows "No extraction is running"** while one is running in game → Moon Mining has not picked it up: check Moon Mining → *Extractions* on auth. The board only repeats what that page knows (it updates every 10 minutes).
- **Times look wrong** → "EVE time" is UTC. "In your time zone" is the **arrival** time, not the current time, converted by Discord with the time zone of the reader's own device: 17:01 EVE time reads 7:01 PM on a device set to UTC+2. (The line was called "Your time" until 2026-10-05; it was renamed after it was mistaken for the current time.)
