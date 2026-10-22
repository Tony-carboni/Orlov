# Runbook 18: juicy killmails in `#juicy-killmails`

**Goal:** a channel under *Member channels* where members chat freely (messages, reactions, GIFs, attachments) and where the bot posts every expensive or rare loss in all of EVE as zKillboard registers it.

**Mechanism:** the kill feed's live reader (runbook 11, zKillboard's R2Z2 files) already reads every killmail in EVE to find ours. Since 2026-10-22 it hands each one to the other bot cogs as an event, and the new cog `orlovbot/cogs/juicy.py` judges it by the owner's rules and posts what qualifies, with the rule in the footer. Nothing else is read from zKillboard. If the live reader is off (`ORLOVBOT_KILLFEED_STREAM = False`) nothing is posted.

## The rules (owner, 2026-10-22)

| Loss | Posted when |
|---|---|
| Supercarrier or titan | always |
| Alliance tournament ship or other limited edition hull (the special edition market group without the giveaway hulls: Gnosis, Praxis, Sunesis, Metamorphosis, shuttles, corvettes, Quafe Miasmos editions, campaign buses, Primae, event ships; the CONCORD ships count as faction hulls) | always |
| Faction hull (navy, pirate, CONCORD, the Marshal) | above 20 B |
| Jump freighter | above 15 B |
| Freighter, Bowhead, Orca, Porpoise | above 8 B |
| T1 hauler, blockade runner, deep space transport | above 10 B |
| Black ops | above 12 B |
| Any other non-capital ship | above 10 B |

Carriers, dreadnoughts, force auxiliaries, Rorquals and lancers are only posted as faction hulls above 20 B. The value is zKillboard's total value of the loss. The thresholds are settings (`ORLOVBOT_JUICY_*_B`, in billions); `ORLOVBOT_JUICY_EXTRA_TYPE_IDS` adds hulls that are posted whatever their value.

## Known values

- Channel: `#juicy-killmails`, category *Member channels* (permissions synced with the category: Family Member may view, post, react, embed, attach; the bot's role *Orlov auth* gets view, send, embed links, history on top).
- Settings on the server: the "Juicy killmails" block of `deploy/conf/local.py.append`, appended to `~/aa-docker/conf/local.py`.
- Cog: `~/aa-docker/orlovbot/cogs/juicy.py` (bind-mounted into the bot container; the repo copy is `deploy/orlovbot/cogs/juicy.py`), registered in `orlovbot/auth_hooks.py`.
- Memory: Django cache keys `orlovbot:juicy:seen` (what was posted, 3 days) and `orlovbot:juicy:type:<id>` (ship groups, a week).

## A. Create the channel (server — local session)

*Done 2026-10-22.* The channel was created through the bot's token with the script in the handoff (category *Member channels*, topic set, one overwrite for *Orlov auth*). By hand it is: Discord → Member channels → Create channel → text, `juicy-killmails`, keep "sync permissions with category", then Edit channel → Permissions → add *Orlov auth* with View, Send messages, Embed links, Read history.

✅ Done when the channel shows under *Member channels* and a member can post a GIF in it.

## B. Switch the feed on (server — local session)

*Done 2026-10-22.* Steps, for reference: copy `deploy/orlovbot/` to the server (old folder kept in `~/backups`), append the "Juicy killmails" block to `conf/local.py`, dry run in a fresh bot container (judge a set of made-up losses, build the post for a real recent titan loss, nothing posted), then restart only the bot container:

```
docker compose -f ~/aa-docker/docker-compose.yml restart allianceauth_discordbot
```

✅ Done when the bot's output lists `orlovbot.cogs.juicy` and, with the next qualifying loss in EVE, "Juicy killmails: posted".

## C. Test post (server — local session)

Set the cache key `orlovbot:juicy:test` to a killmail id (any zKillboard kill); the bot posts it once, marked as a test, at the next idle moment of the live reader.

## Changing things later

- Thresholds: change the `ORLOVBOT_JUICY_*_B` values in `conf/local.py`, restart the bot.
- More hulls posted whatever the value: `ORLOVBOT_JUICY_EXTRA_TYPE_IDS = [type id, ...]`.
- Switch off: `ORLOVBOT_JUICY_CHANNEL = ""`, restart the bot.
- The limited edition list is in the cog (`LIMITED`); EVE adds hulls to the special edition market group now and then.

## Troubleshooting

- Nothing posted for hours: the live reader may be down; the kill feed logs "live feed gave no answer". The 5-minute check of the kill feed does not feed this channel.
- A loss posted twice: the cache was emptied (redis restart) within three days of the loss; harmless.
- "no text channel named #juicy-killmails yet" in the bot log: the channel is missing or renamed.
