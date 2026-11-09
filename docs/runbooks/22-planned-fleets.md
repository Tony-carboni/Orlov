# Runbook 22 — planned fleets: the `#planned-fleets` board and the `/fleet` commands

*Prerequisite: the bot container from runbook 08 is running.*
*Set up 2026-11-09 by the desktop session on the owner's request ("a channel Planned fleets that lists the upcoming fleets, like the moon board, with simple commands to create an event"). Experiment phase: only the owner sees the channel.*

**Goal:** `#planned-fleets` shows one message, "Planned fleets", with every upcoming fleet: name, type, a countdown to formup, the EVE time, the formup place, the FC and extra info, plus the formup time in each reader's own time zone. Anyone with the right role adds a fleet with one slash command; the board updates straight away.

How it works:
- The bot keeps **one** message in `#planned-fleets` and edits it in place (same mechanism as the moon board, `orlovbot/board.py`). Every 10 minutes it recomputes the countdowns; after every `/fleet` command it updates at once.
- Fleets are sorted soonest first under the headings **Forming up now**, **Today**, **This week** and one per month. A fleet stays on the board for 3 hours after its formup time (`ORLOVBOT_FLEET_KEEP_HOURS`), then drops off by itself.
- The list is kept in the Django cache (redis, written to disk), the same place the kill feed remembers what it posted. A bot restart keeps it. Each fleet has a number (`#3`) shown under its block; that number is what `/fleet edit` and `/fleet remove` take.
- All times typed into the commands are **EVE time** (UTC). The line under each block shows the same moment in the reader's own time zone, drawn live by Discord.

## The commands

Type them in any channel where you may use application commands (the board channel itself works). The replies are private (only you see them).

| Command | What it does |
|---|---|
| `/fleet add name type when where [fc] [info]` | puts a fleet on the board. `fc` defaults to your own display name (without the corp ticker). |
| `/fleet edit number [name] [type] [when] [where] [fc] [info]` | changes only the fields you give; `info: -` clears the extra info |
| `/fleet remove number` | takes the fleet off the board |
| `/fleet list` | the same list as a private reply |

The `when` field understands: `11/11 19:00` (day/month, this year or the next if that day has passed), `11/11/2026 19.00`, `2026-11-11 19:00`, `tomorrow 20:00`, `today 23:00`, `saturday 18:00` or `sat 18:00` (the next such weekday), and a bare `19:00` (today, or tomorrow once that hour has passed). Minutes may be written with `:`, `.` or `h`.

Example, the owner's: `/fleet add` with name `Thera camp`, type `PVP`, when `11/11 19:00`, where `Jita 4-4`, fc `Tony Carboni`, info `Tornadoes and high alpha ships`.

Who may use them: the roles in `ORLOVBOT_FLEET_ROLES` (add and edit their own fleets) and `ORLOVBOT_FLEET_ADMIN_ROLES` (edit or remove anyone's). Everyone else gets a private "this is for …" reply. During the experiment both are `["Alliance Director"]`.

## Known values

| Item | Value |
|---|---|
| Channel | `#planned-fleets` (id 1569309272565747772), category `bots`, created 2026-11-09 by the bot |
| Visibility now | `@everyone`, `Family Member` and `Family Friend` denied View; the owner allowed View, Send, Read history, Use application commands; `Orlov auth` the same four rights as on `#moon-board` |
| Settings | block "Planned fleets" at the end of `deploy/conf/local.py.append`, appended to `conf/local.py` |
| Code | `deploy/orlovbot/cogs/fleets.py` → `~/aa-docker/orlovbot/cogs/fleets.py`; registered in `deploy/orlovbot/auth_hooks.py` |
| Check interval | 10 minutes (`CHECK_MINUTES` in `orlovbot/board.py`), plus immediately after each command |
| Bot output | `docker compose logs allianceauth_discordbot`, lines starting `orlovbot.cogs.fleets` and "Planned fleets: board …" |

## A. What was done on 2026-11-09 (local session)

1. Channel `#planned-fleets` created through the bot with the permission overwrites above.
2. `fleets.py` and the updated `auth_hooks.py` copied to `~/aa-docker/orlovbot/`; the settings block appended to `conf/local.py` (copy kept as `~/backups/local.py.pre-fleets`).
3. `manage.py check` and an import of the cog in the gunicorn container (this caught an option description over Discord's 100-character limit before the restart).
4. `docker compose restart allianceauth_discordbot`. Log: "orlovbot.cogs.fleets" among the loaded cogs, "Planned fleets: board posted in #planned-fleets".
5. Within minutes the owner had added fleet `#1 Thera Camp` with `/fleet add`; the board showed it at once.

✅ Done when `#planned-fleets` shows the "Planned fleets" message and `/fleet` appears in the command popup.

## B. Try it (Discord, owner)

1. Open `#planned-fleets`; the board lists the fleets added so far.
2. Type `/fleet add` anywhere, fill in the fields, send. The private reply names the fleet number and the time as Discord shows it for you; the board changes within a second or two.
3. `/fleet edit 2 when: tomorrow 20:00`, then `/fleet remove 2`.
4. `/fleet list` shows the same list privately.

## C. Rollout, once the experiment is over

1. In `conf/local.py` and `deploy/conf/local.py.append` set `ORLOVBOT_FLEET_ROLES = ["Family Member"]` (or whichever role may plan fleets; `ORLOVBOT_FLEET_ADMIN_ROLES` could become `["Alliance Director", "Officer"]`). Restart only the bot container.
2. Channel permissions: `Family Member` View ✅ and Use Application Commands ✅, Send Messages ❌ (the board stays a single tile; commands do not need Send). `Family Friend` as the owner decides. Remove the owner's personal overwrite.
3. Tell members in `#how-to-auth` or the member guide: `/fleet add` puts a fleet on the board.

## Changing things later

| Wish | How |
|---|---|
| Another channel name | rename the channel, or change `ORLOVBOT_FLEET_BOARD_CHANNEL` in both files and restart the bot |
| Keep fleets longer or shorter after formup | `ORLOVBOT_FLEET_KEEP_HOURS`, restart the bot |
| Switch the board off | `ORLOVBOT_FLEET_BOARD_CHANNEL = ""`, restart the bot, delete the message by hand |
| Board message deleted by accident | nothing: the bot posts a new one at its next check |
| Pings before formup, a reminder an hour before, or reading a pasted multi-line text instead of the fields | not built yet; ask a session |

## Troubleshooting

- **"I cannot read the time"** → the `when` text did not match a known form; see the list above. Day comes before month.
- **No board after 10 minutes** → `docker compose logs --tail 100 allianceauth_discordbot | grep -i fleet`. "no text channel named #planned-fleets" means the channel was renamed; "Missing Permissions" means the `Orlov auth` role lost a right on the channel.
- **The command popup does not show /fleet** → the bot registers its commands on start; wait a minute after a restart, or reload Discord (Ctrl+R).
- **A fleet vanished** → it drops off 3 hours after its formup time, or someone removed it (the bot's log has "fleets: #n … removed by …").
