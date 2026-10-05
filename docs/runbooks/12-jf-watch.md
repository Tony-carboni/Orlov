# Runbook 12 — the jump freighter watch: JF losses EVE-wide in `#jf-gank-board`

*Prerequisite: runbook 08 (the bot container `allianceauth_discordbot` is running) and runbook 11 (the kill feed, whose code this builds on).*
*Time: ~10 min. You do section A (Discord). Sections B and C are run by Claude in the **local session**.*

**Goal:** leadership sees every jump freighter that dies in **highsec or lowsec** anywhere in EVE, and how the numbers move. Nullsec and wormhole losses are left out.

Two things appear in `#jf-gank-board`:

| What | Looks like |
|---|---|
| **A post per new loss** | "Rhea lost in Oinasiken (lowsec)", with the victim, who got the final blow and in what ship, how many attackers and which group most of them belong to, the system with its security and region, the ISK value and the time. Blue bar = highsec, orange bar = lowsec. The title links to zKillboard. |
| **The summary**, "Jump freighter losses", always the **last message** of the channel | Losses in the last 24 hours, the last 7 days against the 7 days before, the last 30 days (each split highsec / lowsec, with ISK), a small bar per day for the last 14 days, and for 30 days: losses by hull, the systems with the most losses, and the groups with the most final blows. Ends with the latest loss and "Last checked". |

How it works:
- Every **5 minutes** the bot asks zKillboard for the 200 most recent jump freighter losses (about two months of them) and keeps the highsec and lowsec ones, using zKillboard's own tag on each killmail.
- A loss it has not posted yet, and that is not older than 3 days, gets a post. Then the summary is removed and posted again below it, so it stays at the bottom. When nothing new happened the summary is edited in place.
- It never pings. On its first run it marks the recent losses as known and posts only the summary.
- Roughly 2 to 3 highsec and lowsec jump freighters die per day, so expect a few posts a day.
- "Final blows" credits the alliance (or corp) of the pilot who landed the last shot; with gank fleets that is usually, but not always, the group that organised it.

## Known values

| Item | Value |
|---|---|
| Channel | `#jf-gank-board` (the bot finds it by **name**; the category does not matter) |
| Settings | `ORLOVBOT_JFWATCH_CHANNEL`, `ORLOVBOT_JFWATCH_SPACE` (`["highsec", "lowsec"]`) in `conf/local.py`; block "Jump freighter watch" at the end of `deploy/conf/local.py.append` |
| Code | `deploy/orlovbot/cogs/jfwatch.py` → `~/aa-docker/orlovbot/cogs/jfwatch.py`; it reuses `cogs/killfeed.py` and `board.py` |
| Source | `https://zkillboard.com/api/losses/groupID/902/` (ship group 902 = Jump Freighter: Anshar, Ark, Nomad, Rhea) |
| Check interval | 5 minutes (`CHECK_MINUTES` in `jfwatch.py`) |

---

## A. Create the channel (Discord)

Create the text channel `jf-gank-board` where leadership can read it. Readers: View Channel ✅, Send Messages ❌. The bot's role `Orlov auth`: View Channel ✅, Send Messages ✅, Embed Links ✅, Read Message History ✅.

✅ *Done 2026-10-05 by the owner.*

## B. Switch the watch on (server — local session)

*Done 2026-10-05 16:03 UTC.* Steps, for reference: copy `deploy/orlovbot/` to the server (old folder kept in `~/backups`), append the "Jump freighter watch" block to `conf/local.py` with `>>`, dry run in a fresh process (read zKillboard, build a post and the summary, nothing posted), restart only the bot.

✅ Done when the bot's output lists `orlovbot.cogs.jfwatch` and says "Jump freighter losses: board posted in #jf-gank-board".

## C. Check (Discord)

- The local session can queue one **test post** (the newest existing loss once more, marked "Test post"). Done once on 2026-10-05.
- The summary's "Last checked" entry should never be much older than 5 minutes.

## Changing things later

| Wish | How |
|---|---|
| Include nullsec or wormhole losses | add `"nullsec"` / `"wormhole"` to `ORLOVBOT_JFWATCH_SPACE` in `conf/local.py` and `deploy/`, restart the bot |
| Summary only, no post per loss | not built; ask the local session |
| Other ship classes (freighters, Orcas) | not built; the code takes one ship group, so it is a small change |
| Switch it off | `ORLOVBOT_JFWATCH_CHANNEL = ""`, restart the bot |

## Completion checklist

- [x] `#jf-gank-board` exists (A)
- [x] Watch switched on, summary and test post sent, bot output clean (B, C)
- [ ] Owner confirms the post and the summary look right
- [ ] First real loss appeared by itself, with the summary below it

## Troubleshooting

- **"Last checked" is old** → zKillboard did not answer (the bot skips the round and tries again) or the bot is down; the local session reads `docker compose logs --tail 50 allianceauth_discordbot`.
- **Two summaries** → delete the upper one by hand; the bot uses the newest.
- **A loss on zKillboard is missing** → it was in nullsec or a wormhole, older than 3 days when zKillboard got it, or zKillboard had not tagged its location yet (it is picked up at a later check once tagged).
- **Numbers look low for 30 days** → the summary works from the newest 200 losses of all space; if far more than 200 jump freighters die in 30 days, the oldest days fall outside. At today's rate (about 100 a month) there is ample room.
