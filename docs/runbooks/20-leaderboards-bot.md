# Runbook 20 — The leaderboards bot in `#leaderboards-bot`

**Goal (owner, 2026-10-25):** a channel under *bots* where the Orlov auth bot keeps leaderboards, one board message each, refreshed daily at 14:00 EVE. The first board: **project payouts**, the top 5 pilots by ISK earned from Orlov Arms International's corporation projects in the last 30 days. Two reasons: congratulate the high achievers, and make contributing visible, because the projects are the corp's main source of income.

**Per pilot, not per character.** A character registered in Alliance Auth counts for its main character, so a pilot who adds alts to auth pools their deliveries under one name. A character nobody has registered stands on its own name. That is deliberate: it rewards getting characters into auth.

**Where the numbers come from.** Payouts never touch the corporation journal (EVE pays the member straight from the project's reward pool), so the board uses the Shipyard plugin's payout events: a member's deliveries into a project, read hourly from ESI, times the project's reward per unit. It is the same source as "Project rewards paid out" on the Finance tab. Deliveries made before the plugin started watching projects (14 October 2026) are estimated and spread over the days before; that estimate leaves the 30-day window by mid November.

| What | Where |
|---|---|
| Channel | `#leaderboards-bot`, category *bots*, same permissions as `#moon-board` (members read, only the bot posts) |
| Code | `deploy/orlovbot/cogs/leaderboards.py` → `~/aa-docker/orlovbot/cogs/leaderboards.py`; registered in `deploy/orlovbot/auth_hooks.py` |
| Settings | `ORLOVBOT_LEADERBOARD_CHANNEL`, `_DAYS` (30), `_TOP` (5), `_HOUR` (14) in `~/aa-docker/conf/local.py` (template: `deploy/conf/local.py.append`) |
| Refresh | daily at `ORLOVBOT_LEADERBOARD_HOUR`:00 EVE, and once at every bot restart |

## A. Create the channel (server — local session)

*Done 2026-10-25 13:40 UTC.* Created through the bot's token: text channel `leaderboards-bot` under *bots*, topic set, permission overwrites copied from `#moon-board`. By hand it is: Discord → bots → Create channel → text, `leaderboards-bot`, then Edit channel → Permissions → same as `#moon-board`.

✅ Done when the channel shows under *bots* and members can read but not post in it.

## B. Install the cog (server — local session)

1. Copy `deploy/orlovbot/cogs/leaderboards.py` and `deploy/orlovbot/auth_hooks.py` from the repo to `~/aa-docker/orlovbot/` (Unix line endings).
2. Append the four `ORLOVBOT_LEADERBOARD_*` lines to `~/aa-docker/conf/local.py`.
3. `manage.py check` and an import of `orlovbot.cogs.leaderboards` in a fresh process.
4. `docker compose restart allianceauth_discordbot`, then read the bot's log.

✅ Done when the log shows `orlovbot.cogs.leaderboards` loaded and "Project payouts, top pilots of the last 30 days: board posted in #leaderboards-bot", and the board is in the channel.

## C. Changing it

- Another window or a longer list: change `ORLOVBOT_LEADERBOARD_DAYS` or `_TOP`, restart the bot.
- Another hour: `ORLOVBOT_LEADERBOARD_HOUR`, restart the bot.
- Switch the board off: `ORLOVBOT_LEADERBOARD_CHANNEL = ""`, restart the bot; the old message stays until deleted by hand.
- A second leaderboard goes into the same cog as its own `Board` with its own title; the channel then holds one message per board.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "no text channel named #leaderboards-bot yet" in the bot log | The channel is missing or renamed; section A. |
| The board says "No project payouts in this period yet" | The Shipyard projects read has not run, or no contributions in the window; check the Corp projects tab. |
| A pilot appears twice | One of the characters is not registered in auth; once it is, the next refresh folds it into the main. |
| Numbers differ from the Finance tab's "Project rewards paid out" | The tab counts the reporting period, the board the last 30 days; both come from the same payout events. |
