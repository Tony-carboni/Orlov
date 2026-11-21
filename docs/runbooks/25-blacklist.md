# Runbook 25 — the blacklist and its morning check in `#oarmi-directors`

*Prerequisite: the bot container from runbook 08.*
*Set up 2026-11-21 by the desktop session on the owner's request: "start a blacklist log; add N1ko D95 and any other members I asked you to remove in the last month; if we accidentally let these pilots back in, flag it to us in the director chat via the bot; run every morning".*

**Goal:** one list of pilots who were removed and must not come back, and a bot that checks every morning at 08:00 EVE whether any of them is back, in one of three places: an alliance corporation (EVE), member access in auth, or the Discord server. A hit is posted in `#oarmi-directors` with a ping of the `OARMI Director` role and repeats every morning until the pilot is gone again or taken off the list. Nothing is posted when nobody is found.

## The list

The list is the Markdown table in `deploy/orlovbot/blacklist.md`, copied to `~/aa-docker/orlovbot/blacklist.md` on the server (the bot reads the server copy at every check; a changed file needs no restart). Columns: pilot, EVE character id, Discord user id when known, the date, the reason. A known alt gets its own row with "alt of X" in the reason. The bot resolves a missing character id from the name through ESI, so a row with only the name works, but the id is what makes the row survive a rename.

Entries of 2026-11-21:

| Pilot | Why | Where the character is now |
|---|---|---|
| N1KO D95 | removed from OARMI on 19 November after nine days in the corp; the owner's instruction of 21 November | Omega Industrial Group (Forge Consortium); auth account N1KO_D95 (Family Friend, no Discord link) |
| Kitten Kerns | banned from the Discord server by the owner on 14 November (Discord dominikstarz); earlier locked out of Family Member on 20 October | The Order of Omerta (Hole Control); auth account Kitten_Kerns (Family Friend) |
| zzioxx | banned from the Discord server by the owner on 16 November (Discord .amaoui); the link to auth was found in the database backups of before the ban (user 16) | still in OARMI and Family Member in auth on 21 November, so the check flags him until the corp drops him |

Discord bans are read through the bot (Server Settings → Bans holds the same list); a banned account whose auth link is gone is matched through the nightly database backups, where the old Discord link still shows the auth user. Taken off again on 2026-11-21 (owner): Alexander Helugo, listed the same day; his character sits in Wartorn Industries, an alliance corporation, and the owner does not want the daily note for it.

Looked at and not added: Eemar, Masterxxx and MrFreshy_Valterus (lost a director group on 29 October, not removed as members).

## How the check works

- **EVE:** the public ESI affiliation of every character id gives its corporation; the corporation list of the alliance (`ORLOVBOT_ALLIANCE_ID`, The Orlov Family) comes from ESI too, so a corporation that joins the alliance later counts at once. No token needed.
- **Auth:** the character is owned by a user whose state is in `ORLOVBOT_BLACKLIST_STATES` (Family Member only; a Family Friend account is just a registration and is not a hit). The user's Discord link, if any, is also checked on the server.
- **Discord:** the Discord id from the table, or the linked one from auth, is a member of the server (the bot's member cache; the members intent is on).
- The day of the last check is kept in the Django cache, so a restart later the same day does not repeat the note; a restart after 08:00 on a day without a check runs it once.
- `/blacklist` (Alliance Director) shows the list and the current hits, privately; it does not count as the morning check.

## Known values

| Item | Value |
|---|---|
| Channel | `#oarmi-directors` (id 1555298501938905099), `ORLOVBOT_BLACKLIST_CHANNEL` |
| Ping | role `OARMI Director` (id 1561411839336644780), `ORLOVBOT_BLACKLIST_MENTION` |
| Time | 08:00 EVE, `ORLOVBOT_BLACKLIST_HOUR` (same hour as the idle moon reminder, runbook 23) |
| States that count | `["Family Member"]`, `ORLOVBOT_BLACKLIST_STATES` |
| Alliance | 99015337, `ORLOVBOT_ALLIANCE_ID` |
| List | `deploy/orlovbot/blacklist.md` → `~/aa-docker/orlovbot/blacklist.md` (`ORLOVBOT_BLACKLIST_FILE` overrides the path) |
| Settings | block "Blacklist check" at the end of `deploy/conf/local.py.append`, appended to `conf/local.py` (copy kept as `~/backups/local.py.pre-blacklist`) |
| Code | `deploy/orlovbot/cogs/blacklist.py` → `~/aa-docker/orlovbot/cogs/blacklist.py`; registered in `deploy/orlovbot/auth_hooks.py` (copy `~/backups/auth_hooks.py.pre-blacklist`) |
| Bot output | `docker compose logs allianceauth_discordbot`, lines starting `orlovbot.cogs.blacklist` |

The note, per pilot: a red line per place found ("EVE: IN THE ALLIANCE, corp Wartorn Industries", "Auth: MEMBER ACCESS, user …, state …", "Discord: ON THE SERVER, nickname") and "Listed: date, reason".

## A. What was done on 2026-11-21 (local session)

1. `blacklist.md`, `cogs/blacklist.py` and the updated `auth_hooks.py` copied to `~/aa-docker/orlovbot/`; a dry run in the bot container read both rows and found Alexander Helugo in Wartorn Industries.
2. The settings block appended to `conf/local.py`.
3. `docker compose restart allianceauth_discordbot`. Log: `orlovbot.cogs.blacklist` among the loaded cogs, then "blacklist: 1 of 2 pilots found, posted in #oarmi-directors" (the catch-up note for the day).

✅ Done when `#oarmi-directors` shows "Blacklisted pilot found" with Alexander Helugo and `/blacklist` appears in the command popup.

## B. Adding or removing a pilot (ask a session)

The session adds the row in `deploy/orlovbot/blacklist.md` (name, character id from ESI, Discord id if the pilot was on the server, date, reason), commits, and copies the file to `~/aa-docker/orlovbot/blacklist.md`. The next morning check, or `/blacklist`, uses it. Taking a pilot off is the same with the row deleted.

## Changing things later

| Wish | How |
|---|---|
| Another hour | `ORLOVBOT_BLACKLIST_HOUR` in both files, restart the bot |
| Count Family Friend registrations too | `ORLOVBOT_BLACKLIST_STATES = ["Family Member", "Family Friend"]`, restart the bot |
| No ping, or ping somebody else | `ORLOVBOT_BLACKLIST_MENTION` (`""`, `<@&ROLE_ID>` or `<@USER_ID>`), restart the bot |
| Another channel | `ORLOVBOT_BLACKLIST_CHANNEL`, restart the bot; the bot needs View and Send there |
| Switch it off | `ORLOVBOT_BLACKLIST_CHANNEL = ""`, restart the bot (`/blacklist` keeps working) |

## Troubleshooting

- **No note although a pilot is back** → `docker compose logs --tail 100 allianceauth_discordbot | grep blacklist`. "nobody found" means the three checks all came back empty: an auth account with the Family Friend state does not count, and a Discord member without a Discord id in the table and without an auth link cannot be matched. "the check failed" with a traceback usually means ESI was down; the next morning retries.
- **The note repeats within one day** → the cache lost the day marker (redis restarted); harmless.
- **A row is ignored** → it must have five cells between pipes; a reason with a pipe character in it breaks the row.
