# Runbook 23 — the idle moon reminder in `#oarmi-directors`

*Prerequisite: the bot container from runbook 08 and Moon Mining from runbook 07.*
*Set up 2026-11-19 by the desktop session on the owner's request: "if a corp-owned moon has a pop, but no new extraction is set for it after 24 hours, send a notification every morning to the oarmi-director channel so I don't forget to set a new one".*

**Goal:** every morning at 08:00 EVE the bot looks at our refineries. Each one whose last extraction popped (fired, auto-fractured or cancelled) more than 24 hours ago, with no new extraction started since, is listed in one message in `#oarmi-directors`, with a ping of the `OARMI Director` role. When every refinery has an extraction running, nothing is posted. The note comes back every morning until the extraction is set.

How it works:
- The bot reads the same Moon Mining data as the moon board (the corps registered under Moon Mining → Add Owner; today the holding corp with the three Orlov Mining Facilities). It does not look at the public moons.
- An extraction counts as running while Moon Mining has it as *started* or *ready*. The end of the last one is the latest of fractured, cancelled and auto-fracture time.
- The day of the last note is kept in the Django cache (redis), so a bot restart later the same day does not repeat it; a restart after 08:00 on a day without a note posts it once, straight away.
- `/idlemoons` (Alliance Director) runs the same check on request and answers privately; it does not count as the morning note.

## Known values

| Item | Value |
|---|---|
| Channel | `#oarmi-directors` (id 1555298501938905099), visible to the `OARMI Director` role only (tony, Hamu) |
| Ping | role `OARMI Director` (id 1561411839336644780), `ORLOVBOT_MOON_REMINDER_MENTION` |
| Time | 08:00 EVE, `ORLOVBOT_MOON_REMINDER_HOUR` |
| Threshold | 24 hours after the pop, `ORLOVBOT_MOON_REMINDER_IDLE_HOURS` |
| Settings | block "Idle moon reminder" at the end of `deploy/conf/local.py.append`, appended to `conf/local.py` (copy kept as `~/backups/local.py.pre-moonreminder`) |
| Code | `deploy/orlovbot/cogs/moonreminder.py` → `~/aa-docker/orlovbot/cogs/moonreminder.py`; registered in `deploy/orlovbot/auth_hooks.py` |
| Bot output | `docker compose logs allianceauth_discordbot`, lines starting `orlovbot.cogs.moonreminder` |

The note, per refinery: the refinery and its moon, "Popped: 6d 18h ago (Thu 12 Nov 18:02 EVE)" in orange, red from three days on, and "Next: NOT SET (start a new extraction in the Structure Browser)". The footer repeats the threshold and the hour.

## A. What was done on 2026-11-19 (local session)

1. `moonreminder.py` and the updated `auth_hooks.py` copied to `~/aa-docker/orlovbot/`; a dry run of the check in the gunicorn container listed Ambeke (popped 12 November) and Saatuban (popped 13 November), Piekura running until 20 November.
2. The settings block appended to `conf/local.py`; `manage.py check` clean.
3. `docker compose restart allianceauth_discordbot`. Log: `orlovbot.cogs.moonreminder` among the loaded cogs, then "moon reminder: posted in #oarmi-directors" (the catch-up note for the day, since it was past 08:00).

✅ Done when `#oarmi-directors` shows "Moons waiting for a new extraction" and `/idlemoons` appears in the command popup.

## B. Setting the extraction (in game, owner)

Structure Browser → the refinery → Moon Drill → set the extraction. Moon Mining picks the new extraction up within its next update (every few minutes to an hour); from then on the refinery leaves the note. The moon board (runbook 09) shows the new arrival time.

## Changing things later

| Wish | How |
|---|---|
| Another hour | `ORLOVBOT_MOON_REMINDER_HOUR` in both files, restart the bot |
| Earlier or later than 24 h | `ORLOVBOT_MOON_REMINDER_IDLE_HOURS`, restart the bot |
| No ping, or ping somebody else | `ORLOVBOT_MOON_REMINDER_MENTION` (`""`, `<@&ROLE_ID>` or `<@USER_ID>`), restart the bot |
| Another channel | `ORLOVBOT_MOON_REMINDER_CHANNEL`, restart the bot; the bot needs View and Send there |
| Switch it off | `ORLOVBOT_MOON_REMINDER_CHANNEL = ""`, restart the bot |
| A refinery of another corp | register that corp under Moon Mining → Add Owner (runbook 07 E); it is included automatically |

## Troubleshooting

- **No note although a moon is idle** → `docker compose logs --tail 100 allianceauth_discordbot | grep "moon reminder"`. "every refinery has an extraction running" means Moon Mining still has an extraction as started or ready: check Moon Mining → Extractions on auth. "no text channel named" means the channel was renamed.
- **The note repeats within one day** → the cache lost the day marker (redis restarted without its dump); harmless.
- **The note names a moon whose extraction was just set** → Moon Mining has not read the structure yet; wait for its next update.
