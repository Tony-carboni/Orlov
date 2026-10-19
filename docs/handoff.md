# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-19 (19:00 UTC) — desktop session → any session

**Runbook / topic:** the directors' balance sheet of 19 October (`docs/finance/2026-10-19-oarmi-balance-sheet.pdf`), Shipyard 0.14.1 (runbook 13 C), and two owner's rules for the books.

**Done.**
- **Sheet of 19 October, 18:50 EVE**: master wallet 2,764.8 M, active projects' pool 2,292.4 M, Heavy Water 1,990,000 units at 108 = 214.9 M, project goods bought since the baseline and not sold 89.4 M at cost (first in, first out matching of Shipyard 0.14), Caldari State LP 50,000 at 800 = 40.0 M: 5,401.5 M, result **+401.5 M** above the 5 B. Section 2 reconciles to it exactly: project goods sold in Jita +187.8, Heavy Water sold in Piekura +0.4 profit (10,000 at 149.9 less 108 cost), escrow of a corp buy order placed before the baseline returned +149.5, Raitaru tax transferred from GWON +77.0, fees and tax −8.0, rewards paid to members −94.6 (fall of the pool), goods they bought still held +89.4, LP bought 0.0 (cash into LP at cost). Not counted: Director division 3,221.2 M; older project stock ≈ 525 M at cost (603 M Jita buy); 13.6 M structure income still in GWON's wallet. Fuel: Athanors 192 blocks a day, 105.8 M per 30 days at Oxygen 18,360; 5.2 M burned since the baseline; Raitaru sponsored.
- The owner asked why Heavy Water showed −1.1 M: the sale (+1.5 M) sat inside "goods sold" and the −1.1 M was the stock leaving at cost; the sheet now shows one Heavy Water line with the +0.4 M profit. Correction to the sheet of 18 October: its "17:30 EVE" was the owner's local time; the figures were read at about 16:33 EVE.
- **Shipyard 0.14.1**: the 0.14.0 corp ledger and the structure ledger overwrote each other's shared journal entries every hour; fixed with a separate table (release paragraph in runbook 13). Backup `aa-db-2026-10-19-1852.sql.gz`.
- **Owner's rules, saved in memory:** (1) the directors' sheet covers movements since the date of the last State of the Union post (this once: since the 18 Oct baseline); (2) the corp buys **Caldari State LP at 800 ISK**; each payment leaves a corp wallet division with a reason like "50.000 LP": scan the corp journal (`CorpJournalEntry`) for them and summarise. The first one, 40.0 M for 50,000 LP from the master wallet between 18:44 and 18:49 EVE today, showed in the balance but not yet in the journal (ESI journal cache until 19:25); the next hourly read picks it up.

**Owner has to do by hand.** Share the sheet with the directors. Look at the seven graphs on the Corp projects tab and say which to keep. Still open: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3.

**Next.** Next sheet: movements since the newest State of the Union post; LP from the journal scan.

---

## 2026-10-18 (19:00 UTC) — desktop session → any session

**Runbook / topic:** **Shipyard 0.14.0: history graphs on the Corp projects tab** (runbook 13 C release paragraph has the details).

**Done.** Seven graphs with a days / weeks / every-N-days switch and a date range (paid to members, money in and out of projects, paid out against sold, result of sold goods, buyback margin per material, m³ delivered, members taking part); the hourly projects task also copies OARMI's wallet journal and market transactions; sales are matched first in, first out to project deliveries, ores through their minerals. Fixed: "paid out" no longer counts the refunds of closed projects (the tab showed 4.7 B, the members earned 732 M). Released: backup `aa-db-2026-10-18-1832.sql.gz`, migration 0020, build, 91 tests, collectstatic, `up -d`, nginx; first ledger read done by hand (3,601 journal entries, 197 transactions). Verified: page 200, all seven charts draw (Chart.js 4.4.1), 0 gunicorn errors.

**Findings for the books.** Matched so far: 185.2 M of sales against 163.6 M of project cost (Pyerite, Zero-Point Condensate, Mexallon, Crystalline Isogen, Heavy Water from ice, Hydrocarbons, Silicates). Stock from projects not sold: 550.7 M at cost, 640.6 M at Jita buy. Buyback paid between 83 and 106 % of today's Jita value (ice 102 % as delivered but 83 % reprocessed; Omber 106 % as delivered). Unmatched corp sales: one 5,086 M Tritanium sale on 6 Oct (owner's stock, before the baseline) and 96 M of donated Heavy Water.

**Owner has to do by hand.** Look at the seven graphs on /shipyard/projects/ and say which to keep; the rest can go. Still open: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3.

**Next.** Trim the graphs to the owner's choice.

---

## 2026-10-18 (18:45 UTC) — desktop session → any session

**Runbook / topic:** **the corporation's books on 18 October and the first balance sheet for the directors** (`docs/finance/2026-10-18-oarmi-balance-sheet.pdf`, built with reportlab from `scratchpad/balance_sheet_pdf.py`; the rules of the 5 B baseline are in the 09:40 entry below).

**Done (read-only, nothing changed on the server).**
- Position at 17:30 EVE against the 5 B baseline: master wallet division 1 **2,576.3 M**, reward ISK in the 26 active projects **2,369.6 M** (fresh `projects.refresh()`), Heavy Water stock at buy value **216.0 M**, buyback material still on sale in Jita **44.6 M** at list (Pyerite 1,725,104 at 16.97, Hydrocarbons 33,190 at 459.70; 42.6 M at Jita buy) = **5,206.5 M**, result **+206.5 M**. Division 7 (Director) 3,221.2 M excluded.
- Since the baseline: seven buyback materials sold in Jita for 143.2 M gross (Zero-Point Condensate 61.0, Pyerite 44.1, Mexallon 16.6, Crystalline Isogen-10 14.0, Hydrocarbons 5.5, Silicates 2.0), proceeds in division 1; 5.5 M moon-mining tax from Ryaku711; projects pot down 17.4 M (rewards paid); 4.5 M broker fee and tax. No Heavy Water sold since the 18th. The buyback material came in through Deliver Item projects paid before the baseline, so its sales are new money. Catherine Frey placed the corporation orders (visible through her character-orders scope with `is_corporation`); no OARMI token carries `esi-markets.read_corporation_orders.v1`.
- **Fuel** (section 3 of the sheet), from EVE's dogma: Standup Moon Drill I 5 blocks/h, Manufacturing Plant I 12, Research Lab I 12, Reprocessing Facility I 10; Athanor service bonus −20 %, Raitaru −25 % (engineering services only). Online services per the structures app: Raitaru manufacturing + research lab + reprocessing = 28/h = 672/day; each Athanor moon drill 4/h = 96/day. Total 864 blocks/day; at the cheapest block (Nitrogen 17,890 at Jita) **15.5 M/day, 463.7 M per 30 days** (Raitaru 360.7, each Athanor 51.5). Fuel in the bays, prepaid by GWON, about 668 M (Raitaru to 21 Nov, Athanor I to 26 Dec, Athanor II to 11 Jan). The owner said "both structures"; the sheet shows all three and says so.
- Outlook in the sheet: fuel −463.7 M a month against the structure corp's industry-tax income (65.1 M in the last 7 days, members only, run-rate about 280 M), plus 43 M of open buyback orders and 84 M of Heavy Water upside: about −57 M a month if nothing else changes. Fuel and that income are GWON's, shown side by side for the directors.

- **Owner's rule (18:55 UTC): the Raitaru's fuel is sponsored by a private individual and counts as 0**; the structure income (industry job tax at the Raitaru, Structure income tab; 6.4 M since midnight, 65.1 M in 7 days) counts as corporation income; the two Athanors' fuel (103.1 M per 30 days) stays a cost. The sheet was regenerated with that: outlook about +304 M a month. Note: the Structure income tab has no excluded payers set, so the owner's own jobs are inside the 65.1 M.

**Owner has to do by hand.** Share the PDF with the directors (it is in the repo and was sent in chat). Month-end per the 09:40 entry.

**Next.** Nothing queued.

---

## 2026-10-18 (09:50 UTC) — desktop session → any session

**Runbook / topic:** **SRP from the kill feed, runbook 17** (owner's story of 2026-10-18), **Doctrines 0.4.0** (commit `600b16f` pinned, migration 0007, backup `aa-db-2026-10-18-0933.sql.gz`; `requirements.txt.pre-doctrines-0.4.0`, `local.py.pre-srp`, `killfeed.py.pre-srp` in `~/backups`), 36 tests.

**Done.**
- `SrpRequest` in the Doctrines plugin, one per zKillboard kill id (unique). Created by the kill feed cog when a member **replies "SRP"** to one of the bot's loss posts in #zkillboard (`on_message` in `deploy/orlovbot/cogs/killfeed.py`, copied to `~/aa-docker/orlovbot/cogs/` and the bot restarted), or by an agent by hand on the page. The payout is the **doctrine's figure**: the matching doctrine fit's cost × the ship's SRP percentage (never the killmail's value). Standard fit = every module, rig and subsystem of the doctrine fit was on the lost ship; otherwise, or for a hull no doctrine carries, or a pilot outside the alliance, an **ad-hoc** request (status "to review") with the reason, for the agent to price and approve.
- The page https://doctrines.orlovfamily.space/doctrines/srp/ (permission `doctrines.srp_agent`, given directly to the owner's user; the SRP link in the top bar): tabs Open / To review / Paid / Rejected / All; copy buttons for the pilot's name, the amount (digits) and the kill id; Approve (with payout), Paid, Reject, Reopen; Add by hand; Check the wallet.
- The matcher `doctrines.tasks.srp_match_payments` (beat `doctrines_srp_match_payments`, hourly at :50; `DOCTRINES_SRP_WALLET_DIVISION = 2` in `conf/local.py`, both also in `deploy/conf/local.py.append`) reads the SRP wallet's journal (OARMI division 2) with the Shipyard's production-corp token and marks a request paid when an outgoing entry carries the kill id in its reason or description. **The token exists** (the owner connected Catherine Frey on My business with the three scopes the same morning, and she holds the Accountant role): the wallet read gives 200, the matcher ran once (0 journal entries in division 2 yet). Division balances at 09:55 UTC: master wallet (1) 2,546.5 M, SRP (2) 0, Director (7) 3,221.2 M; the owner still has to fund the SRP division.
- The handoff file's entries were out of order after a merge (two 2026-10-18 entries below 2026-10-17 ones); sorted newest first again.

**Also (11:20 UTC):** Hamu added to `Corp Director`; the Discord channels `#oarmi-corp` (corp_OARMI only) and `#oarmi-directors` (new hidden auth group and Discord role `OARMI Director`: the owner and Hamu) created through the bot with the full chat set, details in `docs/design/membership.md`.

**Owner has to do by hand** (runbook 17 A)
- #zkillboard: let members send messages (replies) in the channel.
- Fund the SRP wallet (division 2, 0 ISK now); pay SRP from it with the kill id in the reason.
- Try it: reply `SRP` to a red loss post; the bot answers with the request; the page lists it.
- Still open: import the corporation fits, the sample doctrine, the landing text, runbook 16 E, the items of the entries below.

### Next — any session
When the owner reports the token: run `doctrines.services.srp.match_payments()` once from the shell and confirm the journal reads (no 403). If the bot does not answer an SRP reply: `docker compose logs --since 10m allianceauth_discordbot | grep -i srp`.

---

---

## 2026-10-18 (09:40 UTC) — desktop session → any session

**Also in this entry, from 07:40 UTC (folded in so it stays within the five entries kept):** **the corporation's books: the 5 B baseline** (owner's rule, 2026-10-18, first separation of corp money from the owner's own wallets).

**The rule.** Until today the owner's wallets and the corporation's (Orlov Arms International, OARMI, corp id 98843356) were one pot. From 2026-10-18 the corporation has a **working budget of 5 B ISK**, made of, at the time of writing: **2,397 M liquid in the master wallet division**, **2,387 M of reward ISK still in the 26 active corp projects** (read from EVE at 07:24 EVE this morning, 49 projects in all), and **216 M of Heavy Water stock** (2,000,000 units at the buy value of 108, listed at 149.9 in Piekura). The 5 B is an **interest-free, perpetual loan from the owner** to the corporation, extractable one day when the corp is rich enough; until then it sits as buffer. **It counts as 0 ISK of corp money**: the corporation's result from now on is everything above or below that 5 B baseline (liquid master wallet + reward ISK still in projects + stock at buy value, minus 5 B).

**Director division:** a completely separate financial part, never corp money; it is the owner's characters' shared wallet. Leave it out of every corp figure.

**Sources for the figures:** the project rewards from the Shipyard's Corp projects snapshots (`shipyard.services.projects.refresh()` then `CorpProject` rows with state Active, field `reward_remaining`); the master wallet balance readable since 2026-10-18 09:55 UTC through Catherine Frey's token (`doctrines.services.srp.wallet_token()`, ESI corporations/98843356/wallets/): 2,546.5 M in division 1 at that time, against the owner's 2,397 M figure of the morning; Heavy Water per the entry below.

**Owner has to do by hand**
- Master wallet access for sessions (set up 2026-10-18 08:05 UTC): `SHIPYARD_PRODUCTION_SCOPES` in `conf/local.py` now lists jobs + corporation wallets + divisions (copy `local.py.pre-production-scopes` in `~/backups`; `deploy/conf/local.py.append` updated). The owner gives **Catherine Frey** the **Accountant** role in OARMI in game (Factory Manager for the jobs), then My business → **Connect the jobs** → EVE login as Catherine Frey → accept the three scopes. That one token serves the jobs refresh and the wallet reads (`business.token()`).

### Next — any session
Month-end (end of October 2026): the corporation's result = master wallet liquid + reward ISK in active projects + Heavy Water stock at buy value, minus 5 B; plus the Heavy Water profit per the entry below. Director division excluded.

*The Heavy Water part of the entry:*

**Runbook / topic:** **Heavy Water sales in Piekura** (owner's rule for the books, 2026-10-18) and the Saatuban mining ledger, both read for the next alliance state message.

**Heavy Water, the owner's rule.** Tommy McPhee (the owner's alt) sells Heavy Water for the Orcas at 120 ISK a unit at Piekura - Freeport Giant Mini-Mart. Everything sold up to and including 2026-10-17 was **donated stock**: book it as pure profit, and **the counter of sold Heavy Water stands at 0 as of 2026-10-18**. From today the corporation **buys** Heavy Water from the master wallet division and puts it back up for sale, so from today on a sale has a cost of goods. For the record, the donated period (first sale 2026-10-08, last 2026-10-17 19:32 EVE, Member Audit transactions of Tommy McPhee): 879,151 units for 105.5 M, of which 250,000 units / 30.0 M to the owner's own alt carbondnb (stock moved, not income) and 629,151 units / 75.5 M to twelve other pilots (100,000 of those to the member Sabbard). Jita at the time of reading: lowest sell 108.9, highest buy 99.99. **First purchase, 2026-10-18:** 2,000,000 units bought by **direct trade** (not a market order), paid from Tommy McPhee's wallet: **216 M ISK, 108 ISK a unit** (owner's figure; it appears in his wallet **journal** as a player trade debit of 2026-10-18, not in the market transactions). **Book this batch at a buy value of 108 ISK a unit.** Listed 2026-10-18 at **149.9 ISK a unit** (the sale price is still read from the transactions at month end, in case it changes). **Profit is recorded at the end of the month** (first time end of October 2026): units sold since 2026-10-18 × their sale price, minus the batches they came from at their buy value (this one 108), **minus the sales taxes**: both the broker fee charged when listing (journal ref type brokers_fee) and the transaction tax taken on each sale (ref type transaction_tax), from Tommy McPhee's wallet journal for the month. Rule from the owner: purchases by direct trade are the cost of goods for the units sold afterwards. Any future "how much Heavy Water did we sell" question counts from 2026-10-18 00:00 EVE and compares against the purchase price (market orders on the master wallet division, or direct trades in the journal); the source for the sales is Tommy McPhee's wallet transactions in Member Audit (the corp wallet feed in the Shipyard carries the structure tax journal only).

**Saatuban ledger.** The Saatuban Athanor (Orlov Mining Facility II) reports miners per EVE day through aa-moonmining's ledger (refinery id 1055997584926; the Piekura one is 1055901489178). 2026-10-17: 18 characters, 362,791 units, 185 M at the module's Jita prices; Sabbard 53 M, Hamu 19.8 M, Tommy McPhee 19.4 M on top; one outsider, Velorra Lenoir of Tax Evasion Corp 81, mined 39,254 Bitumens (14.5 M). The same table is in auth under Moon Mining → the refinery → Mining ledger.

**Also (06:55 UTC): Shipyard 0.13.5** (backup `aa-db-2026-10-18-0653.sql.gz`; 0.13.4 an hour earlier had it at 90 % of the Jita buy): the Reprocessing tab has a **BB** column in front of the price points, the alliance buyback price per unit = **85 % of the output value** (`SHIPYARD_BUYBACK_SHARE`, default 0.85). No migration; released per runbook 13 C.

**Owner has to do by hand**
- Buy the first Heavy Water stock from the master wallet division and relist it; from then on sales minus purchases is the profit.
- Still open from the entries below: import the corporation fits, the landing text, delete the sample doctrine, runbook 16 E.

### Next — any session
Nothing on the server. If the owner asks for the Heavy Water figures again: sales since 2026-10-18 from Member Audit (character Tommy McPhee, type Heavy Water, location Piekura, is_buy false) against the corporation's purchases (the master wallet division's market transactions; the corp wallet scope is on the structure corp token).

---

