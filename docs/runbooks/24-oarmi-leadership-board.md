# Runbook 24 — the OARMI leadership board in `#oarmi-leadership-team`

*Prerequisite: the bot container from runbook 08.*
*Set up 2026-11-19 by the desktop session on the owner's request: "a new channel under bots, available only to OARMI corp members, no typing, same as the moon board; a bot message updated once a day: Directors, Officers".*

**Goal:** `#oarmi-leadership-team` shows one message, "OARMI leadership team", with the corp's directors and officers by main character name. OARMI members can read it, nobody can type there, the bot keeps it current.

How it works:
- Same mechanism as the moon board (`orlovbot/board.py`): one message, edited in place, with a "Last checked" line.
- The names come from the **auth groups** `OARMI Director` and `OARMI Officer` (the Discord roles of the same names follow those groups), so adding a director or officer in auth changes both the role and the board. The board lists each member's main character, sorted by name.
- Redrawn once a day at 06:00 EVE (`ORLOVBOT_LEADERSHIP_HOUR`) and at every bot start.

## Known values

| Item | Value |
|---|---|
| Channel | `#oarmi-leadership-team` (id 1572961154941067324), category `bots`, created 2026-11-19 by the bot |
| Visibility | `corp_OARMI` View and Read history only (allow 66560, the moon board's member pattern); `@everyone`, `Family Member` and `Family Friend` denied everything on the channel; `Orlov auth` the moon board's rights |
| Sections | `ORLOVBOT_LEADERSHIP_GROUPS`: Directors ← `OARMI Director`, Officers ← `OARMI Officer` |
| Settings | block "OARMI leadership board" at the end of `deploy/conf/local.py.append`, appended to `conf/local.py` (copy kept as `~/backups/local.py.pre-leadership`) |
| Code | `deploy/orlovbot/cogs/leadership.py` → `~/aa-docker/orlovbot/cogs/leadership.py`; registered in `deploy/orlovbot/auth_hooks.py` |
| Bot output | `docker compose logs allianceauth_discordbot`, lines "OARMI leadership team: board …" |

## A. What was done on 2026-11-19 (local session)

1. Channel created through the bot with the overwrites above.
2. `leadership.py` and the updated `auth_hooks.py` copied to `~/aa-docker/orlovbot/`; the settings block appended to `conf/local.py`; a dry run in the gunicorn container showed Directors: Catherine Frey, Hamu; Officers: Bern Akiga, Braadslee, Francis01, JordayTM, Logan Grishnar, Sabbard.
3. `docker compose restart allianceauth_discordbot`. Log: "OARMI leadership team: board posted in #oarmi-leadership-team".

✅ Done when `#oarmi-leadership-team` shows the board under bots and an OARMI member can read but not type.

## Changing things later

| Wish | How |
|---|---|
| Add or remove a director or officer | auth admin → Groups → `OARMI Director` or `OARMI Officer`; the role syncs at once, the board at the next redraw (06:00 EVE) or bot restart |
| Another section, e.g. the CEO | add `{"title": "CEO", "group": "CEO"}` to `ORLOVBOT_LEADERSHIP_GROUPS` in both files, restart the bot (the CEO group holds outside CEOs too; make an OARMI-only group first if that matters) |
| Redraw more often | `ORLOVBOT_LEADERSHIP_HOUR` is one hour a day; for faster updates ask a session to put the loop on a shorter interval |
| Open it to the whole alliance | allow `Family Member` View and Read history on the channel (66560) |
| Switch it off | `ORLOVBOT_LEADERSHIP_CHANNEL = ""`, restart the bot, delete the message by hand |

## Troubleshooting

- **A name is missing** → the person is not in the auth group, or their account has no main character (then the auth username shows instead).
- **No board** → `docker compose logs --tail 100 allianceauth_discordbot | grep -i leadership`; "no text channel named" means the channel was renamed.
