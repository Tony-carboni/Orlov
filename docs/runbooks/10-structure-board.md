# Runbook 10 — the structure board: structure and war status for directors

*Prerequisite: runbook 08 (bot running) and runbook 07 section E (the structure-owning corp is registered under Structures → Add Owner).*
*Time: ~10 min. You do section A (Discord) and section D (tell the local session the profile names). Sections B and C are run by Claude in the **local session**.*

**Goal:** a channel `#structure-board` in the directors category that always shows one message, "Structure status", kept current by the bot, the same way as the moon board (runbook 09). The board itself never pings; three alerts in the same channel do (see "Alerts" below).

What the board shows:

| Per owning corp | Source | How fresh |
|---|---|---|
| War eligible: yes / no | EVE's public corporation info | re-read every hour |
| Wars declared or running, who declared, when fighting starts, when the war ends | the war notifications EVE sends to the registered character, as collected by the Structures app | notifications are fetched every 5 minutes |
| "Structure data read from EVE" with a live "x minutes ago" | the Structures app | it reads structures every 30 minutes |

| Per structure | Source |
|---|---|
| State: "shield vulnerable (normal)", or in capitals with the timer when reinforced, anchoring, unanchoring | Structures app |
| Power: full power / LOW POWER / ABANDONED | Structures app |
| Fuel: days left (hours when under two days), e.g. "32 days left"; hovering it shows the exact run-out date in EVE time, clicking it opens Structures on auth; flagged when less than 7 days are left. The number is refreshed by the bot's 10-minute check, so it changes once a day | Structures app |
| Services: all online, or the list of offline ones | Structures app |
| Profile: the structure profile | EVE's API (number only) + the name list in `conf/local.py`, re-read every hour |

The message's colour bar is green when everything is fine, orange when something needs attention (fuel under 7 days, low power, a service offline) and red when it is urgent (a war, a structure that is not in its normal state, abandoned).

## Alerts (pings in `#structure-board`)

Added 2026-10-05 on the owner's request. Besides the board, the bot posts a short message starting with `@everyone` in the same channel:

| Alert | When | Repeats |
|---|---|---|
| **War declared** | a war appears that the board did not know yet (ours or against us), with who and when fighting starts | no, once per war |
| **Structure needs attention: fuel** | fuel under 7 days, or no fuel and the structure in low power | once every 24 hours while it lasts |
| **Structure needs attention: services offline** | one or more services of the structure are offline | once every 24 hours while it lasts |

- Fuel and services of one structure go into **one** message. If a second problem shows up later the same day (fuel was low, now a service drops too), the bot pings again at once with both, and the 24 hours start over.
- The channel stays tidy: a new daily reminder replaces the previous one for that structure, and when the problem is fixed (refuelled, service online, war over) the bot **removes** its alert. So besides the board the channel only ever holds alerts that are still true.
- `@everyone` in this channel reaches only the people who can see the channel, i.e. the directors.
- The bot checks every 10 minutes, and the Structures app reads EVE every 30 minutes, so an alert can lag the game by up to about 40 minutes.
- What was already sent is remembered outside the bot (in the cache), so restarting the bot or the server does not ping again. If that memory is ever wiped, every alert that is still true is sent once more.
- Switch all alerts off with `ORLOVBOT_STRUCTURE_ALERTS = False` in `conf/local.py`; change who is pinged with `ORLOVBOT_STRUCTURE_ALERT_MENTION` (for example a role mention instead of `@everyone`). Restart the bot afterwards.
- **Test:** the local session can queue one harmless test alert ("Test alert from the structure board. Nothing is wrong"); the bot posts it at its next check and removes it at the check after. Done once on 2026-10-05 11:53 UTC.

Things to know:
- **War status comes from notifications, not from a war register.** EVE's API has no "wars of this corp" lookup. The board starts a war at the declaration notice and ends it at the invalidated / retracted / surrender / HQ-removed notice, or when the corp stops being war eligible. If EVE never sends an end notice, the board keeps showing the war. So it errs towards showing a war that is already over; confirm in game before acting on it.
- **Profiles:** EVE's API gives each structure a profile *number* and never the name. Until the names are filled in (section D) the board shows the number, e.g. `Profile: #243511`.
- The board repeats what auth knows. If "Structure data read from EVE" is hours old, the token of the registered character has a problem: see Troubleshooting.
- Only structures of corps registered under Structures → Add Owner appear. Today that is GWON with two structures.

## Known values

| Item | Value |
|---|---|
| Channel | `#structure-board` (the bot finds it by **name**) |
| Settings | `ORLOVBOT_STRUCTURE_BOARD_CHANNEL` and `ORLOVBOT_STRUCTURE_PROFILES` in `conf/local.py` (block "Structure board" at the end of `deploy/conf/local.py.append`) |
| Code | `deploy/orlovbot/cogs/structures.py` and the shared `deploy/orlovbot/board.py` → `~/aa-docker/orlovbot/` |
| Bot role in Discord | `Orlov auth` |
| Profile numbers seen 2026-10-05 | Orlov Family Facilities (Raitaru, Isikano): `243511`; Orlov Mining Facility I (Athanor, Piekura): `244593` |

---

## A. Create the channel (Discord, 3 min)

1. Right-click the directors category → **Create Channel** → Text → name `structure-board` (exactly this).
2. Channel → **Edit Channel → Permissions**:
   - `@everyone`: View Channel ❌
   - `Alliance Director` (and `Corp Director` if they should see it): View Channel ✅, Send Messages ❌
   - `Orlov auth` (the bot): View Channel ✅, Send Messages ✅, Embed Links ✅, Read Message History ✅
3. **Save Changes**.

✅ Done when the channel exists, only directors see it, and the bot may post. *Done 2026-10-05: the channel existed when the board was switched on.*

## B. Switch the board on (server — local session)

*Done 2026-10-05 11:40 UTC.* Steps, for reference:

1. Copy `deploy/orlovbot/` to `~/aa-docker/orlovbot/` (Unix line endings); keep a copy of the old folder in `~/backups`.
2. Dry run in a fresh process in the bot container: import the module, run `collect()` and `build_embed()`, print the result. Nothing is posted.
3. Append the "Structure board" block from `deploy/conf/local.py.append` to `conf/local.py` with `>>`.
4. `manage.py check`, then restart **only** the bot: `docker compose restart allianceauth_discordbot`.

✅ Done when the bot's output lists `orlovbot.cogs.structures` under "Cogs Loaded" and says "Structure status: board posted in #structure-board".

## C. Check (Discord)

`#structure-board` shows one message "Structure status" with the corp, its war line, and one entry per structure. Compare fuel dates and states with the Structure Browser in game.

## D. Give the profiles their names

1. In game: Structure Browser → *My Structures*. The *Profile* column shows which profile each structure uses.
2. Tell the local session, for example: "Orlov Family Facilities uses profile Kaas, Orlov Mining Facility I uses profile Orlov".
3. The local session adds the pairs to `ORLOVBOT_STRUCTURE_PROFILES` in `conf/local.py` and in `deploy/conf/local.py.append`, and restarts the bot. The board then shows the names.

When you make a new profile or move a structure to another one, the board shows the new number until its name is added the same way.

## Changing things later

| Wish | How |
|---|---|
| A second corp's structures | Structures → Add Owner on auth with a director of that corp; they appear on the board by themselves |
| Another fuel warning threshold | `FUEL_WARNING_DAYS` in `structures.py` |
| Switch the board off | `ORLOVBOT_STRUCTURE_BOARD_CHANNEL = ""`, restart the bot, delete the message |
| Other fuel threshold or repeat interval for the alerts | `FUEL_WARNING_DAYS` and `ALERT_REPEAT` in `structures.py` |
| No alerts, board only | `ORLOVBOT_STRUCTURE_ALERTS = False`, restart the bot |

## Completion checklist

- [x] `#structure-board` exists (A)
- [x] Board switched on, bot output clean (B)
- [ ] Owner confirms the board is right and only directors see the channel (C)
- [ ] Profile names filled in (D)
- [x] Alerts switched on; logic self-tested (13 scenarios) and one live test ping sent
- [ ] Owner confirms the test ping arrived in `#structure-board`

## Troubleshooting

- **No board message** → local session reads `docker compose logs --tail 50 allianceauth_discordbot`. "no text channel named" = name differs; "Missing Permissions" / "Missing Access" = the `Orlov auth` role lacks one of the four permissions in A2.
- **"Structure data read from EVE" is hours old** → the Structures app cannot read EVE: on auth open Structures, or admin → Structures → Owners, and check the owner's status; usually the character's token was revoked (changed password, left the corp, lost the Director role). Fix with Structures → Add Owner again.
- **A war shows that is over** → see "Things to know". The local session can check which notification is missing.
- **Profile shows `#number`** → section D.
- **An alert did not ping** → the message must start with a highlighted `@everyone`. If it shows as plain text, the `Orlov auth` role lost "Mention @everyone" on the channel (it has Administrator today, which includes it).
- **The same alert every 10 minutes** → should be impossible (the bot records an alert before sending it); if it happens set `ORLOVBOT_STRUCTURE_ALERTS = False`, restart the bot, and have the local session read the bot's output.
- **War eligible: unknown** → EVE's API did not answer; it is retried at the next check.
