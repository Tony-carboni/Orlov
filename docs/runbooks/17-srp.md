# Runbook 17 — SRP: ship replacement from the kill feed

*Prerequisites: runbook 11 (the kill feed in `#zkillboard`) and runbook 16 (the doctrines site). Time: 10 min for you (Discord and the wallet token), the rest is done by the local session.*

**Goal:** a pilot who loses a ship on an SRP fleet replies `SRP` to the loss in `#zkillboard`. The bot records the request on the SRP page of the doctrines site with the **doctrine's figure** for that fit (cost of the doctrine fitting at Jita × the ship's SRP percentage), so cargo and odd modules cannot inflate it. A loss that is not a doctrine fit is an **ad-hoc** request for an SRP agent to review. The zKillboard kill id keeps requests unique. An agent pays from the **SRP wallet** (OARMI, division 2) with the **kill id in the reason**; the hourly matcher then marks the request paid. Several agents can work the same list without any administration.

How it works (short): `SrpRequest` rows in the Doctrines plugin (`apps/doctrines`, 0.4.0); the kill feed cog (`deploy/orlovbot/cogs/killfeed.py`) listens for replies that start with "SRP" under its own loss posts; the page is https://doctrines.orlovfamily.space/doctrines/srp/ for members with the permission `doctrines | general | Can handle SRP requests`; the task `doctrines_srp_match_payments` reads the SRP wallet's journal at :50 every hour with the Shipyard's production-corp token (Catherine Frey, Accountant role, connected on My business).

## Known values

| Item | Value |
|---|---|
| Page | https://doctrines.orlovfamily.space/doctrines/srp/ (also under auth at `/doctrines/srp/`) |
| Who may use it | permission `doctrines.srp_agent`; today: the owner only (given directly to the user) |
| Payout | doctrine fit cost (hull + fit + drones + cargo of the **doctrine** fitting, Jita lowest sell) × the ship's SRP percentage; the doctrine's percent unless the ship has its own (logi 100 %) |
| Standard fit | every module, rig and subsystem of the doctrine fit was on the lost ship (extra modules do not matter) |
| Ad hoc | modules missing, no doctrine for the hull, the pilot not in the alliance, or an unpriced doctrine item; the agent sets or confirms the payout and approves |
| SRP wallet | OARMI (corp 98843356) division 2; `DOCTRINES_SRP_WALLET_DIVISION` in `conf/local.py` |
| Matcher | `doctrines.tasks.srp_match_payments`, hourly at :50; also the **Check the wallet** button on the page |

---

## A. Discord and the wallet (you, 10 min)

1. **Let members reply in `#zkillboard`.** Channel settings → Permissions → the member role: *Send Messages* on (the bot's posts stay the bot's; members only reply). ✅ A member can type in the channel.
2. **The wallet token.** Catherine Frey holds the **Accountant** role in OARMI (Corporation → Members → Role Management), then https://shipyards.orlovfamily.space/business/ → **Connect the jobs** → EVE login as Catherine Frey → accept the three scopes (jobs, corporation wallets, divisions). ✅ The SRP page no longer shows "no wallet token yet" at the bottom.

## B. Release (local session, done 2026-10-18)

Runbook 13 C for the Doctrines plugin: backup, pin, build, throwaway `check` and `migrate --plan`, migration 0007, collectstatic, `up -d`, nginx; the beat entry `doctrines_srp_match_payments` and `DOCTRINES_SRP_WALLET_DIVISION = 2` appended to `conf/local.py`; the cog copied to `~/aa-docker/orlovbot/cogs/killfeed.py` and the bot restarted; the permission given to the owner's user.

## C. The flow (everyone)

1. **The pilot:** finds the red loss post in `#zkillboard`, replies to it (Reply, not a new message) with `SRP`. The bot answers at once: the request number, the pilot, the ship, the payout (or "ad-hoc request, an SRP agent reviews it"). A second `SRP` on the same loss answers "requested before".
2. **The agent:** opens the SRP page. The **Open** tab is the pay list: copy the pilot's name, copy the amount, copy the kill id (the three small copy icons). In game: corporation wallet → the SRP division → *Give money* (or the transfer to the character) with the **kill id as the reason**. Within the hour the matcher marks the request **Paid**; **Check the wallet** does it now; **Paid** marks it by hand when needed.
3. **To review:** an ad-hoc request shows why (modules missing, no doctrine, outsider). Set the payout in the box, **Approve** (it moves to Open), or reject it.
4. **By hand:** the *Add by hand* box takes a zKillboard link or a kill id, for a loss nobody replied to.

## Troubleshooting

- **The bot does not answer an `SRP` reply** → the reply has to be a Discord *reply* to the bot's post, in the kill feed channel, starting with SRP. Bot log: `docker compose logs --since 10m allianceauth_discordbot | grep SRP`.
- **"I could not read that kill from zKillboard"** → zKillboard or EVE did not answer; the agent adds the kill by hand on the page, or the pilot tries again in a minute.
- **A request never turns Paid** → the transfer's reason must contain the kill id (digits); the matcher only reads division 2; the token must exist (A2). Mark it paid by hand and check the reason next time.
- **Wrong payout** → the doctrine ship's cost or SRP percent in the admin; reopen the request after a fix recomputes nothing (the figure is fixed at request time): reject and add the kill again.
