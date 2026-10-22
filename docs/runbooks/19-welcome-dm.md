# Runbook 19 — the welcome DM: every new Discord member gets the link to #how-to-get-roles

*2026-10-22, desktop session. Owner's request: "can our bot auto-DM everyone who joins our discord with a link to #how-to-get-roles?"*

**Goal:** the moment someone joins the alliance Discord, the auth bot (*Orlov auth*) sends them a direct message with the link to `#how-to-get-roles` and a two-line summary of what to do. If the person's privacy settings refuse DMs from server members, the bot posts the same note in `#how-to-get-roles` itself, mentioning them, so they still find it.

**Mechanism:** a bot cog, `orlovbot/cogs/welcome.py` (repo copy `deploy/orlovbot/cogs/welcome.py`), listening to Discord's member-join event. The bot already runs with the Members intent (allianceauth-discordbot turns it on), which is what makes join events arrive. Registered in `orlovbot/auth_hooks.py` with the other cogs. Bots that join are ignored.

| Setting in `conf/local.py` | Default | Meaning |
|---|---|---|
| `ORLOVBOT_WELCOME` | `True` | `False` switches the DM off without removing the cog |
| `ORLOVBOT_WELCOME_CHANNEL_ID` | `1555292924374417471` | the channel the DM links to (`#how-to-get-roles`) |

The text of the DM is in the cog (`message()`): welcome, "To see more channels you need your roles" (the owner's wording of 2026-10-22: the server is not only for alliance members), the link, "log in to auth with your EVE character, link your Discord there, and the roles follow by themselves", and where to ask. Change it there and restart the bot.

## A. Install (local session, server)

Done 2026-10-22 by the desktop session: the cog and the updated `auth_hooks.py` copied into `~/aa-docker/orlovbot/` (CRLF stripped), the two settings appended to `conf/local.py` (copy `local.py.pre-welcome` in `~/backups`), `docker compose restart allianceauth_discordbot`, the bot's log shows the cog loaded.

For a later change: edit the repo copy, then copy it to the server and restart the bot. On the **PC**, from the repo folder:

```bash
sed "s/\r$//" deploy/orlovbot/cogs/welcome.py | ssh orlov "cat > ~/aa-docker/orlovbot/cogs/welcome.py"
```

```bash
ssh orlov "docker compose -f ~/aa-docker/docker-compose.yml restart allianceauth_discordbot"
```

✅ Done when the bot's log (`docker compose logs --since 2m allianceauth_discordbot`) shows no error after the restart.

## B. Check (you)

Join the server with a second Discord account, or ask the next newcomer: within a few seconds a DM from *Orlov auth* arrives with the link. If their DMs are closed, the note appears in `#how-to-get-roles` with a mention instead. The bot's log carries one line per join (`welcome: DM sent to …` or `… does not accept DMs …`).

Note: Discord only lets a bot DM people who share a server with it, which a new member does by definition; the bot cannot DM someone who left again.
