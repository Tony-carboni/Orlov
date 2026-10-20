# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-20 (14:40 UTC) — desktop session → any session

**Runbook / topic:** **the accidental corporation sell orders of 2026-10-20 and Shipyard 0.21.0** (runbook 13 C release paragraph).

**What happened.** Six sell orders meant for the owner's own wallet were put up on the corporation (Catherine Frey) between 13:30 and 14:13 EVE: Drake Navy Issue 3, Drekavac 2, Prophecy Navy Issue 7, Caracal Navy Issue 10, Omen Navy Issue 8, Helium Fuel Block 20,000. One Drekavac sold at 13:48 for 147,800,000. The corporation paid 39,847,273 in listing fees (Drake 5,782,104, Drekavac 4,319,408, Prophecy 12,806,257, Caracal 6,194,172, Omen 4,999,759, Helium 5,745,573) and 4,988,250 sales tax on the Drekavac. **Net in the master wallet from the mistake: +102,964,477 ISK.** The owner transfers exactly that from the master wallet (division 1) to his own wallet with a reason that contains the word "accidental"; the corporation is then back at zero and the fees are the owner's own cost. The Drake, Drekavac and Prophecy orders were cancelled; Caracal, Omen and Helium were still open at 14:35 EVE, the owner cancels them. Anything that sells before they are cancelled is a new sale and tax line to flag the same way (a local session: `books.ignore_entries`), and the settlement amount grows by the sale minus its tax.

**Done.**
- **Shipyard 0.21.0** released (commit `a251dc3` pinned, migration 0027, backup `aa-db-2026-10-20-1422.sql.gz`): the Finance tab leaves out flagged journal lines, by id (admin: Shipyard → ignored journal lines) or by a reason matching the ignore patterns (`SHIPYARD_BOOKS_IGNORE_REASONS`, default "accidental"). The page and the PDF say how many lines are left out and their net.
- The eight lines above are flagged (reason "accidental corporation orders 2026-10-20 (settled to personal wallet)"). The sheet reconciles (gap 0) and shows 8 lines left out, +102,964,477 together; result at 14:35 EVE +195.9 M above the 5 B with liquid ISK 2,569.6 M (the real wallet is 103.0 M higher until the settlement lands).
- Rule for the books from now on: **a transfer that corrects a mistake carries "accidental" in its reason** and drops out of the books by itself; sales, taxes and fees of a mistake are flagged by id.

**Owner has to do by hand.** Cancel the Caracal, Omen and Helium orders. Transfer 102,964,477 ISK from the master wallet to his own wallet, reason containing "accidental" (for example "accidental corp orders settlement"). Still open from earlier: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Next.** After the transfer: check the Finance tab shows 9 lines left out with a net of 0 (any session, read-only). If something sold before the orders were cancelled: tell a local session, it flags the lines and gives the new settlement amount.

---

## 2026-10-19 (19:40 UTC) — desktop session → any session

**Runbook / topic:** **Shipyard 0.15.0: the LP conversion tab** (runbook 13 C release paragraph).

**Done.** New tab at /shipyard/lp/ (full access, between Scrapmetal and My industry): every offer of the State Protectorate loyalty store (ESI public route, `SHIPYARD_LP_STORE_CORP_ID` 1000180) valued at Jita lowest sell, minus the ISK charge and the inputs at Jita sell, as net ISK per LP; after-fees rate with the member's own sales tax and broker fee; Jita daily volume and sell-order depth; blueprint copies show the price a copy must fetch for 900 ISK/LP (`SHIPYARD_LP_TARGET_ISK_PER_LP`), per copy when the offer gives several. Filters, presets, column picker, resizable columns, Refresh for managers. Released: commit `a48ee89` pinned, backup `aa-db-2026-10-19-1924.sql.gz`, migration 0022, beat entries `shipyard_refresh_lp_store` (03:50) and `shipyard_refresh_lp_prices` (:45) appended to `conf/local.py` (copy `local.py.pre-0.15.0` in `~/backups`) and to `deploy/conf/local.py.append`, build, 95 tests, `up -d`, nginx; first read by hand: 387 offers, 464 types priced, 334 volumes (one 400 from ESI history for a crate type that is not on the market, harmless). Page 200 as tony, 0 errors.

**First reading of the store (before fees).** 68 item offers reach 900 ISK/LP or more, 54 reach 1,000. The very top is distorted by rare inputs and thin markets: Caldari Listening Outpost 290,080/LP (100 LP plus a 7.7 M Decoder Package; 3 sold a day), the Penumbral Shadows SKINs around 3,000/LP at list prices with almost no trade, High-grade Talon implants 2,100 to 4,100/LP (1 or 2 a day). Among liquid items: Caldari Navy Light Missile Launcher 2,175/LP (20 a day). Blueprint copies: the navy frigate copies (Hookbill, Griffin Navy Issue, Heron Navy Issue) must fetch 5.4 to 5.6 M a copy, Corax and Cormorant Navy Issue 14.3 M.

**Owner has to do by hand.** Open the tab, sort and filter; say what to change (for example a Jita buy column, hiding SKINs, or the target rate). Still open from earlier: the DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Next.** Nothing queued.

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

## 2026-10-18 (09:50 UTC) — desktop session → any session

**Runbook / topic:** **SRP from the kill feed, runbook 17** (owner's story of 2026-10-18), **Doctrines 0.4.0** (commit `600b16f` pinned, migration 0007, backup `aa-db-2026-10-18-0933.sql.gz`; `requirements.txt.pre-doctrines-0.4.0`, `local.py.pre-srp`, `killfeed.py.pre-srp` in `~/backups`), 36 tests.

**Done.**
- `SrpRequest` in the Doctrines plugin, one per zKillboard kill id (unique). Created by the kill feed cog when a member **replies "SRP"** to one of the bot's loss posts in #zkillboard (`on_message` in `deploy/orlovbot/cogs/killfeed.py`, copied to `~/aa-docker/orlovbot/cogs/` and the bot restarted), or by an agent by hand on the page. The payout is the **doctrine's figure**: the matching doctrine fit's cost × the ship's SRP percentage (never the killmail's value). Standard fit = every module, rig and subsystem of the doctrine fit was on the lost ship; otherwise, or for a hull no doctrine carries, or a pilot outside the alliance, an **ad-hoc** request (status "to review") with the reason, for the agent to price and approve.
- The page https://doctrines.orlovfamily.space/doctrines/srp/ (permission `doctrines.srp_agent`, given directly to the owner's user; the SRP link in the top bar): tabs Open / To review / Paid / Rejected / All; copy buttons for the pilot's name, the amount (digits) and the kill id; Approve (with payout), Paid, Reject, Reopen; Add by hand; Check the wallet.
- The matcher `doctrines.tasks.srp_match_payments` (beat `doctrines_srp_match_payments`, hourly at :50; `DOCTRINES_SRP_WALLET_DIVISION = 2` in `conf/local.py`, both also in `deploy/conf/local.py.append`) reads the SRP wallet's journal (OARMI division 2) with the Shipyard's production-corp token and marks a request paid when an outgoing entry carries the kill id in its reason or description. **The token exists** (the owner connected Catherine Frey on My business with the three scopes the same morning, and she holds the Accountant role): the wallet read gives 200, the matcher ran once (0 journal entries in division 2 yet). Division balances at 09:55 UTC: master wallet (1) 2,546.5 M, SRP (2) 0, Director (7) 3,221.2 M; the owner still has to fund the SRP division.
- The handoff file's entries were out of order after a merge (two 2026-10-18 entries below 2026-10-17 ones); sorted newest first again.

**Also (2026-10-20, 11:30 UTC): Shipyard 0.20.0**: the Finance tab's section 2 counts from the newest State of the Alliance post (the post's date, 00:00 EVE) and adds up to the result minus that opening; the hourly task opens the period by itself from `posts.json` on the alliance site (`site/alliance/build.py` now writes it; copied to `~/aa-docker/alliance-site/`). This first window runs from the 18 October baseline, because the 14 October post is older. When a State of the Alliance post is published: run `python site/alliance/build.py` and copy `dist/` to the server as runbook 15 says, including `posts.json`; the period opens within the hour.

**Also (2026-10-20, 10:40 UTC): Shipyard 0.19.0**: the Finance tab's sections 1 and 2 as clickable categories (liquid ISK, reward ISK in projects, stock listed, physical items in stock, goods held from projects, loyalty points; project buyback sales, project buyback rewards, LP conversion, stock sales, market orders and fees, transfers and deposits); corrected withdrawals dropped; the owner's second LP purchase (15,000 LP for 12 M) and the redemptions of 08:44 (500 Navy Cap Booster 100, 80 more 800s) in the books. Rule for sessions: after every LP store redemption add a stock batch (admin → Shipyard → stock batches) with the LP used, the input item and units, the ISK and who paid it; the offer terms are on ESI `/loyalty/stores/1000180/offers/`.

**Also (2026-10-20, 09:10 UTC): Shipyard 0.18.2 to 0.18.8** (commit pinned per runbook 13 C, no migrations): both buyback sections of the Finance tab per calendar month in the owner's shape with a summary line; the project section condensed to two clickable lines (ore and ice, other items); broker fees matched to repriced orders through the item's real sale prices; the LP conversion tab's Net and ISK/LP after the viewer's sales tax (figure before tax on hover). Live at 07:41 EVE: +473.4 M; project buybacks +32.0 M net (11 %) on 326.6 M sold, +13.9 M projected on 88.9 M held; LP buybacks +2.5 M net, +0.8 M projected. Open: the owner's question why the LP profit is low was answered (fees fall on the boosters' full value, about 5 % of 103 M); nothing queued.

**Also (2026-10-20, 07:55 UTC): Shipyard 0.18.0 and 0.18.1** (commit `75c4544` pinned, migration 0025, backup `aa-db-2026-10-20-0740.sql.gz`): the Finance tab has sections for **project buybacks** and **LP buybacks and conversions** (LP bought, items to convert, LP store redemptions, booster sales with sales tax and broker fees, net profit, still listed, open buy orders) and the corp's open orders. Entered in the admin as stock batches: the two LP store redemptions of 06:50 (240 Navy Cap Booster 800, 500 Navy Cap Booster 400; 49,000 LP, 740 input boosters, 49 M LP store ISK paid from the master wallet, not from the owner's own wallet as first assumed). The owner's orders scope login worked. When the corp buys LP or converts again: a new stock batch per redemption in the admin (Shipyard → stock batches: LP used, input item and units, ISK paid and by whom). Details in runbook 13 C.

**Also (2026-10-20, 06:05 UTC): corporation market orders scope.** `SHIPYARD_PRODUCTION_SCOPES` in `conf/local.py` now also asks for `esi-markets.read_corporation_orders.v1` (copy `local.py.pre-orders-scope` in `~/backups`; `deploy/conf/local.py.append` updated; gunicorn, workers and beat restarted). Until the owner logs in with Catherine Frey once more on My business → Connect the jobs, `business.token()` finds no token, so the hourly corp jobs read and the SRP wallet check pause (the corp ledger has its own token lookup and keeps running). Next for a session once the token exists: read the corporation's open orders into the Finance tab (listed stock such as the cap boosters bought with the 50,000 LP, ISK in buy-order escrow), and turn the LP into a stock batch once the owner gives the booster type, count and the LP store ISK.

**Also (2026-10-20, 05:50 UTC): Shipyard 0.17.0 and 0.17.1, the Finance tab** (commit `ca77d17` pinned, migrations 0023 and 0024, backups `aa-db-2026-10-20-0537` and `-0543`): the directors' balance sheet as a page on the front door with Download PDF and Read EVE now; the baseline and the Heavy Water batch are in the admin. The hand-made sheet of 20 October (`docs/finance/2026-10-20-oarmi-balance-sheet.pdf`, +393.8 M) was the check: the page gives the same. My earlier chat report of 05:20 (+249.0 M) left out the project goods bought since the baseline and not sold yet (124.8 M at cost) and today's sales; the sheet is the correct figure. Details in runbook 13 C.

**Also (2026-10-20, 05:20 UTC): financial report against the 5 B baseline**, read from EVE through Catherine Frey's token: master wallet 2,683.1 M + rewards left in the 26 active projects 2,311.0 M + Heavy Water stock 1,990,000 × 108 = 214.9 M + 50,000 LP bought for the corp at 40 M (held by Tommy McPhee) = 5,249.0 M, so **+249.0 M over the baseline**. Of that, 149.5 M is a one-off (escrow released 2026-10-18 09:02 from an old corp buy order of carbondnb, money that existed but was not counted in the 5 B), 77.0 M the Raitaru tax deposited by Vieze Jonge Pass, 22.5 M operations (Jita sales of corp stock 187.8 M minus sales tax 6.4 M and broker fees 1.6 M, minus about 158 M paid out to members through projects, plus project funding moved). Heavy Water now sells as a **corporation** sell order issued by Catherine Frey at the Piekura Freeport (2,000,000 listed at 149.9 on 2026-10-18 06:16, broker 3.0 M and SCC 1.5 M paid then; 10,000 sold so far), paid for by a 216 M corp withdrawal to Tommy McPhee on 2026-10-18 05:59; month to date the line is −4.1 M because the listing fees come first. The baseline's 2,397 M was the master wallet right after the owner moved 1,559.6 M to another division at 07:08 and 07:27. Divisions 2 (SRP), 3 (LP Buyback), 4 (Working budget) hold 0; 7 (Director only, 3,221.2 M) is left out. The token lacks `esi-markets.read_corporation_orders.v1`, so open corp orders cannot be read yet.

**Also (2026-10-20, 05:00 UTC): Shipyard 0.16.0** (commit `96312ea` pinned, backup `aa-db-2026-10-20-0457.sql.gz`): the **Member shipyards** tab, owner only, shows the ship dashboard as a new member sees it (default facility and market, no character, the corp's blueprint markup, no own blueprints or prices), saving nothing; details in runbook 13 C. The corp roles guide has the limited-director title (hangars 4 to 7, wallet 4, no Director role) built for Hamu; the owner sets it up in game.

**Also (2026-10-20):** Kitten_Kerns (Discord dominikstarz) locked to Family Friend level by the new state `Family Friend (locked)` (priority 150, by character); details and how to undo in `docs/design/membership.md`.

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

