# Runbook 24 — the leadership board in `#leadership-team`

*Prerequisite: the bot container from runbook 08.*
*Set up 2026-11-19 by the desktop session on the owner's request: "a new channel under bots, available only to OARMI corp members, no typing, same as the moon board; a bot message updated once a day: Directors, Officers".*

**Goal:** `#leadership-team` (created as `#leadership-team` on 19 November, renamed by the owner on 21 November because it goes beyond OARMI) shows one message, "Leadership team", in two clearly marked sections (owner, 2026-11-21): **Alliance leadership** on top (everyone who can see `#corporate-ceos`, CEOs first, then directors; the board does not say how the list is made) and **Per corporation** (one block per corporation, OARMI first: its CEO, its directors, and for OARMI also the officers). OARMI members can read it, nobody can type there, the bot keeps it current.

How it works:
- Same mechanism as the moon board (`orlovbot/board.py`): one message, edited in place, with a "Last checked" line.
- The names come from the **auth groups** `OARMI Director` and `OARMI Officer` (the Discord roles of the same names follow those groups), so adding a director or officer in auth changes both the role and the board. The board lists each member's main character, sorted by name.
- Redrawn once a day at 06:00 EVE (`ORLOVBOT_LEADERSHIP_HOUR`) and at every bot start.
- The alliance section and the per-corporation blocks (2026-11-21) read the **members of the CEO channel** (`ORLOVBOT_LEADERSHIP_CEO_CHANNEL`, `#corporate-ceos`: whoever Discord lets see it, bots excluded; today the `CEO` and `OARMI Director` roles) and group them by the corporation of their main character in auth. The corporations shown are the alliance's per ESI plus any corporation a channel member belongs to (Parallax Ultima, not in the alliance yet), minus `ORLOVBOT_LEADERSHIP_HIDE_CORPS` (Wartorn Industries [W T I], 98701264, left off on 21 November: about to disband, the owner wants no attention on it), the executor corp first, then by name. The **CEO** of each corporation is read from ESI (public) and shown as the Discord account that owns that character; when that character is not on Discord, the corp's channel members with the `CEO` role stand in (NowhereClone is ThatOneClone's alt, so MONO1 shows ThatOneClone as CEO); only with nobody at all is the character named with "not on Discord". Every other channel member of the corp is a **Director** (Auroraee for PARXU, Hamu for OARMI). The OARMI block (`ORLOVBOT_LEADERSHIP_GROUPS_CORP`, 98843356) also carries the auth groups of `ORLOVBOT_LEADERSHIP_GROUPS`: the directors and the officers, labelled Director and Officer. Colours: CEO pink (nearest to the CEO role's violet), Director red, Officer orange. The section titles are `## ` headings (`ORLOVBOT_LEADERSHIP_SECTION_HEADING`), the block titles `### `.
- Looks like the member list (owner, 2026-11-19, twice): each section has a Discord heading (`### `, one size up from the names; `ORLOVBOT_LEADERSHIP_HEADING`) and under it the members by their **Discord display name**, `[OARMI] Tony_Carboni`, the nickname auth sets, in the colour those names have in the right-hand pane, inside an ansi code block. The OARMI roles have no colour of their own, so the directors take Corp Director's dark orange and the officers Officer's amber; Discord's text palette has only eight colours, so the nearest are used: red and orange (`ORLOVBOT_LEADERSHIP_COLOURS`). A member without a Discord link shows as the corp tag (`ORLOVBOT_LEADERSHIP_PREFIX`) plus the main character. Discord cannot colour a heading, nor size text inside a code block, which is why the colour sits on the names, as in the member list.

## Known values

| Item | Value |
|---|---|
| Channel | `#leadership-team` (id 1572961154941067324), category `bots`, created 2026-11-19 by the bot |
| Visibility | `corp_OARMI` View and Read history only (allow 66560, the moon board's member pattern); `@everyone`, `Family Member` and `Family Friend` denied everything on the channel; `Orlov auth` the moon board's rights |
| Sections | `ORLOVBOT_LEADERSHIP_GROUPS`: Directors ← `OARMI Director`, Officers ← `OARMI Officer` |
| Look | heading `### `, names in Directors red, Officers orange (choices: red, orange, green, blue, pink, cyan, white), fallback prefix `[OARMI] ` |
| Settings | block "OARMI leadership board" at the end of `deploy/conf/local.py.append`, appended to `conf/local.py` (copy kept as `~/backups/local.py.pre-leadership`) |
| Code | `deploy/orlovbot/cogs/leadership.py` → `~/aa-docker/orlovbot/cogs/leadership.py`; registered in `deploy/orlovbot/auth_hooks.py` |
| Bot output | `docker compose logs allianceauth_discordbot`, lines "OARMI leadership team: board …" |

## A. What was done on 2026-11-19 (local session)

1. Channel created through the bot with the overwrites above.
2. `leadership.py` and the updated `auth_hooks.py` copied to `~/aa-docker/orlovbot/`; the settings block appended to `conf/local.py`; a dry run in the gunicorn container showed Directors: Catherine Frey, Hamu; Officers: Bern Akiga, Braadslee, Francis01, JordayTM, Logan Grishnar, Sabbard.
3. `docker compose restart allianceauth_discordbot`. Log: "OARMI leadership team: board posted in #oarmi-leadership-team".

✅ Done when `#leadership-team` shows the board under bots and an OARMI member can read but not type.

## B. The alliance sections (2026-11-21, local session)

The owner asked for the board to cover the alliance too, then shaped it in four rounds the same evening: "one message per corp for the leadership team, and one for the alliance as a whole listing all the members of the CEO channel; or all in one message, as long as the sections are clearly marked"; "remove the text about everyone in CEOs, just say alliance leadership; ThatOneClone is a CEO also, Auroraee can be listed as director; NowhereClone is an alt of ThatOneClone, just list ThatOneClone"; "remove W T I altogether for now"; "alliance leadership at the top, then OARMI, then the other corps". Done as one message in that order. The cog was replaced (copy `~/backups/leadership.py.pre-sections`), `ORLOVBOT_LEADERSHIP_CEO_CHANNEL`, `ORLOVBOT_LEADERSHIP_CHANNEL = "leadership-team"` and `ORLOVBOT_LEADERSHIP_HIDE_CORPS` appended to `conf/local.py` (copy `~/backups/local.py.pre-leadership-sections`), the bot restarted; because the board's title changed to "Leadership team", the bot posted a new message and the old "OARMI leadership team" message of 19 November was deleted through the bot. Board of 21:49 UTC: Alliance leadership (Raistlin Kano, ThatOneClone, Tony_Carboni as CEO; Auroraee, Hamu as Director), then OARMI (Tony_Carboni CEO, Hamu Director, six Officers), MONO1 (ThatOneClone CEO), PARXU (Raistlin Kano CEO, Auroraee Director).

✅ Done when the message "Leadership team" in `#leadership-team` shows the two `##` sections in that order.

## Changing things later

| Wish | How |
|---|---|
| Add or remove a director or officer | auth admin → Groups → `OARMI Director` or `OARMI Officer`; the role syncs at once, the board at the next redraw (06:00 EVE) or bot restart |
| Another section, e.g. the CEO | add `{"title": "CEO", "group": "CEO"}` to `ORLOVBOT_LEADERSHIP_GROUPS` in both files, restart the bot (the CEO group holds outside CEOs too; make an OARMI-only group first if that matters) |
| Another colour, heading size or tag | `ORLOVBOT_LEADERSHIP_COLOURS`, `ORLOVBOT_LEADERSHIP_HEADING` (`## ` is bigger still) or `ORLOVBOT_LEADERSHIP_PREFIX` in both files, restart the bot |
| Show W T I again, or hide another corporation | `ORLOVBOT_LEADERSHIP_HIDE_CORPS` (corporation ids), restart the bot |
| The groups in another corporation's block | `ORLOVBOT_LEADERSHIP_GROUPS_CORP`, restart the bot |
| Another CEO channel, or none | `ORLOVBOT_LEADERSHIP_CEO_CHANNEL` (a channel name; a missing channel logs a warning and leaves the alliance sections empty), restart the bot |
| Other section titles | `ORLOVBOT_LEADERSHIP_ALLIANCE_TITLE`, `ORLOVBOT_LEADERSHIP_CORPS_TITLE`, restart the bot |
| Redraw more often | `ORLOVBOT_LEADERSHIP_HOUR` is one hour a day; for faster updates ask a session to put the loop on a shorter interval |
| Open it to the whole alliance | allow `Family Member` View and Read history on the channel (66560) |
| Switch it off | `ORLOVBOT_LEADERSHIP_CHANNEL = ""`, restart the bot, delete the message by hand |

## Troubleshooting

- **A name is missing** → the person is not in the auth group, or their account has no main character (then the auth username shows instead).
- **A name shows as `[OARMI] <character>` instead of the Discord nickname** → that account has no Discord link, or the person left the server.
- **No board** → `docker compose logs --tail 100 allianceauth_discordbot | grep -i leadership`; "no text channel named" means the channel was renamed.
