# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-11-09 (evening UTC) — desktop session (PC) → any session

**Runbook / topic:** the four Fractured Skies navy attack battlecruisers for the Shipyard dashboard (owner's ask of 9 November), and the EVE soundboard (8 November).

**Battlecruisers, what is known.** Fractured Skies ships Tuesday 10 November 11:00 UTC. Expansion notes of 6 November: Naga Navy Issue (cruise missiles and torpedoes; BPC in the State Protectorate store), Oracle Navy Issue (24th Imperial Crusade), Talos Navy Issue (Federal Defense Union), Tornado Fleet Issue (Tribal Liberation Force); every blueprint copy 52,000 LP plus 13 million ISK, no tag mentioned, runs per copy not stated. Checked 9 November: the four names are not in ESI, EVE Ref has no type for them, and none of the four militia stores lists a 52,000 LP offer yet. The catalog needs nothing new: attack battlecruisers (group 1201) are already a hull group, navy hulls are active by default and get their militia LP faction pre-linked by `shipyard_load_ships`; the hourly refresh loads materials and prices for every active ship.

**Prepared.** `deploy/scripts/fractured_skies_bcs_check.py` (PC, plain Python, read-only: ESI name lookup, EVE Ref type, the four stores' offers) and `deploy/scripts/fractured_skies_bcs_add.py` (Django shell on the server, after `shipyard_load_ships`: sets LP faction, 52,000 LP, 13 M ISK, 1 run and a note on the four ShipConfig rows; idempotent).

**Next (local session, on 10 November once the check script shows all four in ESI and EVE Ref, usually a few hours after downtime).** Announce, then: backup with aa-backup.sh; `shipyard_load_ships` in the gunicorn container (rebuilds the catalog from EVE Ref, existing rows keep their flags and config); pipe the add script into the Django shell; `shipyard_refresh`; check the dashboard shows the four under Navy battlecruisers with a build cost and the LP route; compare the runs per copy with the State Protectorate offer in the LP conversion tab and fix `lp_runs` if a copy has more than one run.

**Soundboard (8 November, done).** The owner's EVE client (`C:\CCP\EVE`) holds the English voice bank; its 1,221 clips were split out and named through Wwise's SoundBanksInfo from CCP's resource CDN, decoded with vgmstream. `C:\Users\Toon Budeners\Documents\EVE soundboard\soundboard.html` lists 488 clips in six groups (Aura's 50 spoken notifications, 376 tutorial Aura lines including capacitor none, shields low and down, armor damaged and loss, ammo low and none, plus alarms, targeting, warp and UI beeps); nothing of it is in git (CCP assets). Discord's server soundboard (eight slots at boost tier 0, OGG or MP3 only, converted with the container's ffmpeg, uploaded by the bot as Administrator) carries Target lock, Negative, Docking denied, Negative 3. Four slots free; the owner was asked which capacitor take and what else to put there.

**Owner has to do by hand.** Pick the remaining four soundboard clips. Still open: the 75 M "correction" deposit of 3 November, the C2 entrance board inputs, more officers, the OARMI Director role, the 3-hour refresh, corp_GB44 and corp_1E3, DigitalOcean weekly backups, the stray #pings, the seven project graphs.

---

## 2026-11-08 (18:05 UTC) — desktop session (PC) → any session

**Runbook / topic:** Shipyard 0.39.0 and 0.39.1 (runbook 13 C): donated LP, and the red box that stayed open.

**Done.** 0.39.0: EVE's API has no corporation LP route (checked the ESI spec: wallets return division and balance only, loyalty routes exist per character and for store offers), so donated LP go in through a new admin register, LP donations (model LpDonation, migration 0038: date, units, donor, note). From its date a row adds its LP to the stock at SHIPYARD_LP_STOCK_ISK_PER_LP (800) each, as one "LP donated" movement in the LP category; "LP bought" counts only paid LP; the corporation LP log lists donations and says how many were donated on top. Entered: 68,000 LP dated 8 November 12:00 EVE (the wallet shows 304,000 State Protectorate LP, the books knew 236,000 bought; the 299 Caldari Navy LP are ignored at the owner's word). 0.39.1: the 206 M correction of 15:56 (to Tommy McPhee) was typed "corrections projects" and the default SHIPYARD_BOOKS_PROJECT_FUNDING_REASONS matched only "correction project", so the line fell under the ignore rule and the box stayed at 206 M; default now corrections?\s+projects?. Released per runbook 13 C (backups aa-db-2026-11-08-1750 and -1757, migration 0038 applied, 152 tests, server pinned at 697d977). Sheet after: 304,000 LP in stock worth 243.2 M, "LP donated" +54.4 M, result 802.3 M, period +301.0 M, gap 0, owed 0, box gone (journal read up to 15:56 UTC).

**Findings.** Like a stock batch, a donation dated after the journal's last line waits for the next journal read, so date it an hour or more back. The owner's correction reasons vary in number ("correction projects", "corrections projects"); the pattern now takes both, watch for other spellings in the ignored-lines list.

**Owner by hand.** Nothing. When the wallet's State Protectorate figure and the Finance tab's "LP in stock" differ again, say the wallet figure: the difference goes in as a new LP donations row (admin, or ask a session).

**Open.** Still open from earlier entries: the C2 entrance board inputs, more officers, the OARMI Director role purpose, the 3-hour character refresh, corp_GB44/corp_1E3, DigitalOcean weekly backups, stray #pings, the seven project graphs, the hangar-vs-ledger gap (−462 M at 17:35 EVE today), the radio sound confirmation.

**Next.** Nothing queued; the next step is whatever the owner raises.

## 2026-11-08 (16:20 UTC) — desktop session (PC) → any session

**Runbook / topic:** Shipyard 0.38.3 and 0.38.4 (runbook 13 C), the finance confusion of 7–8 November, runbook 04 E (Eternity Emperor), runbook 09 (moon board, 6 November), runbook 20 (leaderboards hourly, 6 November).

**Done.** 0.38.3: the "LP processed" and "LP in stock" tiles count in thousands (519k LP). 0.38.4: the outside-master box lets the corrections cover the funding lines in date order and lists only the lines still open with the amount open, whatever the project's state, plus the time of the last journal line; SHIPYARD_BOOKS_PROJECT_REPAYMENT_ENTRIES accepts deposits and names the 75 M "correction" deposit of 3 November 13:10 (entry 26228486232) as project money coming back (server conf/local.py and deploy/conf/local.py.append); new setting SHIPYARD_LP_STOCK_ISK_PER_LP = 800: LP in stock are carried at 800 ISK each, LP bought dearer or cheaper book the difference in the "LP bought" movement. Both released per runbook 13 C (backups aa-db-2026-11-08-1602 and -1616, no migration, 151 tests). Eternity Emperor refreshed (C.KC → OARMI, Family Member, nickname set). Earlier this week: moon board keeps a popped moon 12 hours (04b45ca), leaderboards bot refreshes hourly at xx:30 (f8bc576).

**Findings.** The owner's routines, now in memory: a project funded from the wrong wallet is cancelled, remade from the master wallet, and the funding is paid back from the master wallet to the owner's character with "correction projects" (not to division 7); a deposit with a DS code is a direct sale. The confusion of 7–8 November came from the box: it listed the projects by state and named three settled ones while the 206 M it asked for belonged to two cancelled ones (coesite 56 M and Corp buyback Ice 150 M, funded from division 7 at 17:40 on 7 November). At 16:18 UTC the live master wallet is exactly 206 M below the journal copy, so that correction is paid and shows at the next journal read (journal read up to 13:11 UTC). Sheet then: gap 0, owed 0. The hourly flag sent the owner a notification about the two 17:40 lines after the restart.

**Owner by hand.** Nothing. Check the Finance tab after the next journal read: the red box should be gone.

**Open.** Donated LP: the owner says members donated LP to the corporation without a purchase cost; the books only know LP from journal lines ("NNNk LP" withdrawals), and ESI has no corporation LP balance (only /characters/{id}/loyalty/points). They need a way in (a hand-kept register in the admin, or the owner names the units); once in, they count at 800 ISK each like the rest. Also still open from earlier entries: the C2 entrance board inputs, more officers, the OARMI Director role purpose, the 3-hour character refresh, corp_GB44/corp_1E3, DigitalOcean weekly backups, stray #pings, the seven project graphs, the hangar-vs-ledger gap, the radio sound confirmation.

**Next.** Whichever session the owner answers in: build the donated-LP register once he says how many LP and from whom.

## 2026-11-05 (10:15 UTC) — desktop session (PC) → any session

**Runbook / topic:** the wallet reconciliation after the project corrections of 4 November (owner's request of 4 November 23:25), Shipyard 0.38.0 (runbook 13 C release paragraph).

**Done.** Diagnostic script (scratchpad, read-only; journal since 2 November, every project since 1 October with its funding wallet and refunds, the owner-to-corp ledger since the 18 October baseline, books.compute). Findings: private project funding since the baseline 1,756.3 M, repaid 1,576.3 M with "correction projects" plus the 360 M "corrections" of 5 November 08:23 (laptop session's advice, executed by the owner) = the 180 M refund of the privately funded scordite project + the extra 180 M "correction" deposit of 4 November 22:22. Project side fully reconciled; sheet gap 0.0, live wallets equal the journal copy. **Shipyard 0.38.0** (commit `3ba8052` pinned, backup `aa-db-2026-11-05-1006.sql.gz`, 147 tests, no migration): `SHIPYARD_BOOKS_PROJECT_REPAYMENT_ENTRIES` (entry id to ISK) counts part of a master-wallet withdrawal as project repayment; set on the server and in the deploy template to the 360 M line with 180 M (`conf/local.py`, copy `local.py.pre-repayment-entries`). The Finance tab's "owed to the funding wallet" box is gone (funded 1,756.3 = corrected 1,756.3). The 100 M LP-store purchase of 31 October 13:58 (24th Imperial Crusade, master wallet) flagged by id against the owner's 100 M "correction LP store purchase" deposit. The scheduled 01:27 run of 5 November never fired (session restarted overnight; session-only timers die with it); the 09:00 reminder task can be deleted.

**Later the same day, Shipyard 0.38.1** (owner: "get rid of this whole section about cap boosters in the Finance page and report; bulk LP sales only going forward"): section 4 "LP buybacks and conversions" removed from the Finance tab and the PDF, Structure fuel is section 4, the position row reads "LP held for sale"; LP bought and sold still show in Movements, the period tiles and the position. No migration. Released per runbook 13 C at 17:05 UTC: commit 9bad3fc pinned, image rebuilt, 147 tests, backup aa-db-2026-11-05-1702.sql.gz, containers recreated, nginx restarted; the live Finance page shows sections 1 to 3 and "4. Structure fuel", the position row "39,000 LP held for sale", the PDF is built from the same module.

**2026-11-06 08:40 UTC, Shipyard 0.38.2** (owner: "I still want the tiles about LP in stock, LP processed, net profit on LP; just not the cap boosters table"): section 4 is "Loyalty points" again on the Finance tab and in the PDF, Structure fuel is 5. Four tiles (net profit on LP, margin on what sold, LP processed since the period base with the LP sold and what it brought, LP in stock at cost) and one summary line per month; the per-month conversion and product-sales tables and "Buying now" are gone for good. Commit f3d2fbf pinned, 147 tests, backup aa-db-2026-11-06-0831.sql.gz, containers recreated, nginx restarted, verified live as the owner (November: 519,375 LP bought at 800 and sold at 866, +34.5 M; 39,000 LP in stock).

**Open.** The 75 M "correction" deposit of 3 November 13:10 has no corp-side counterpart: the LP-store purchases of 2 November (500 M and 150 M) were paid from division 7, the owner's own wallet, and no master-wallet LP-store line exists around then. The sheet now shows it as "Wallet as EVE shows it, against the journal copy +75 M". Either the corp sends 75 M back to the owner, or the owner names what it settled and the lines get flagged.

**Owner has to do by hand.** Decide the 75 M. Still open from before: the C2 entrance board inputs (map id, share token, channel, staging system), more officers, the OARMI Director role, the 3-hour refresh, corp_GB44 and corp_1E3, DigitalOcean weekly backups, the stray #pings, the seven project graphs.

**Next.** Nothing queued.

---
## 2026-11-02 (08:20 UTC) — desktop session (PC) → any session

**Runbook / topic:** **radio in comms** (runbook 21, research 10), from the owner's ask for background music in the voice channel that each member can switch off or turn down for themselves.

**Done.** Research note `docs/research/10-discord-background-music.md` (options A own cog, B public radio bot, C Watch Together; the per-listener control is Discord's own user volume on the bot). Owner chose A. The custom image now carries ffmpeg and libopus0 (`deploy/custom.dockerfile`, apt as root for that layer) and `PyNaCl==1.5.0` (`conf/requirements.txt`); backup `aa-db-2026-11-02-0810.sql.gz`, images rebuilt, throwaway check: ffmpeg 7.1.5, PyNaCl, opus loaded, cog imports. Cog `orlovbot.cogs.radio` (`/radio on [station]`, `/radio next`, `/radio stations`, `/radio off`, `/radio volume`; Family Member role; leaves an empty channel within a minute; presence shows the station; a dropped stream rolls to the next). Settings `ORLOVBOT_RADIO_STATIONS` (SomaFM Space Station Soma, Drone Zone, Groove Salad; Nightwave Plaza) and `ORLOVBOT_RADIO_VOLUME = 0.3` in conf/local.py and the template. Containers recreated 08:13 UTC, the bot lists the cog among its loaded cogs, every container up. Stream decode test from the container: all stations decode. **Later the same morning:** py-cord 2.8 needs its voice extra (`PyNaCl 1.6`, `davey`); Discord refuses voice without end-to-end encryption (close code 4017), so DAVE stays on; davey 0.2.0 (published that day) gave silent audio with py-cord 2.8.1, pinned to **0.1.7**; the cog got a sequence guard (a stopped source no longer restarts the station loop), a deferred reply, a 20 s connect bound, the voice library's debug log in the container log, and `ORLOVBOT_RADIO_CHANNELS = ["music", "voice1"]` so it plays only in `Voice1 - music bot`. 21 stations by genre, Lofi first (the default). `#music-bot-instructions` holds the bot's embed with the instructions, read-only for everyone. **Not yet confirmed by the owner: that listeners hear sound after the davey pin.**

**Owner has to do by hand.** Join a voice channel, `/radio on`, listen; right-click the bot for the personal level. Tell members (the member guide does not mention it yet). Still open from the earlier entries: the 3-hour character refresh, `corp_GB44` and `corp_1E3`, DigitalOcean weekly backups, the stray #pings, the seven project graphs, the `OARMI Director` role's purpose.

**Next.** Nothing queued.

---

## 2026-10-31 (20:15 UTC) — desktop session (PC) → any session

**Runbook / topic:** Shipyard 0.37.0 (runbook 13 C; `docs/runbooks/13-shipyard-plugin.md` release paragraph), the blue alliance's wormhole map (`docs/research/09-blue-alliance-wormhole-map.md`), and a note on an unregistered pilot.

**Done.** **Shipyard 0.37.0** (commit `d08157e` pinned, backup `aa-db-2026-10-31-2007.sql.gz`, migration 0036, 145 tests): new permission `shipyard.refresh_prices`; whoever holds it sees the Refresh button on the ship dashboard, Reprocessing and Scrapmetal and the "Read prices now" button on Bargains without manager rights. Granted to Hamu's account directly (his permissions are all direct: dashboard_access, reprocessing_access, refresh_prices); all four tabs rendered as him show the button. Observation during the checks: `makemigrations --check` keeps reporting an index rename on `lpsnapshot` (`shipyard_lp_charact_6b1f2e_idx` to `..._00de85_idx`); cosmetic, not in a migration, unchanged by this release. **Research 09:** the blue alliance maps on wormhole.systems (not Pathfinder); the doc has the access model (alliance-wide grants, our alliance id 99015337), the API (share token or personal token, GET /api/maps/{id} with home, statics, connections with mass and lifetime), the three built-in Discord alerts, and the proposed path: Viewer access for the alliance, an `entrance` cog for orlovbot that keeps a C2 entrance embed up to date, a proximity alert to our webhook. Mirroring in our own mapper rejected (no sync exists). **Zypher Komeer** (Discord helavade) asked to auth 2026-10-31, locked out of Discord; `docs/reference/known-alts.md`.

**Owner has to do by hand.** For the entrance board: ask the blue alliance for alliance-level Viewer access (id 99015337), the map id, and a share token (or mint a personal token with one of our characters once access is granted); say which channel and which staging system to count jumps from. Open from before: more officers, the OARMI Director role's purpose, the 3-hour refresh, corp_GB44 and corp_1E3, DigitalOcean weekly backups, the stray #pings, the seven project graphs.

**Next.** When the map id and token arrive: build the entrance cog (`deploy/orlovbot/cogs/`), runbook 21, settings in conf/local.py, restart the bot container.

---
