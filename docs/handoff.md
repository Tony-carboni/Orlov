# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-21 (19:30 UTC) — desktop session → any session

**Runbook / topic:** **Shipyard 0.24.0: Register a direct sale** (runbook 13 C), replacing the reason-text approach of 0.23.x after the owner found EVE's transfer reason holds 40 characters (his test: the line stopped at the last 0 of 40).

**Done.** Finance → **Register a direct sale**: paste the items as the game copies them, Quote (ore and ice at 95 % of the Reprocessing tab's value, never above Jita buy; other items at Jita buy; the projects' cost and profit per line, first in first out, ores through their minerals), Register → a code `DS-XXXX` for the deposit's reason. When the deposit with the code appears in the journal, the registered lines leave the goods held and the sale is marked matched; pending registrations are listed with a delete button. Section 3 of the sheet has one line per month, **Direct sale of goods** (deposits, cost, profit), inside "Net profit so far"; the sales of 20 October (Atmospheric Gases, 1.7 M against 7.6 M of cost) and 21 October (200.4 M against 179.6 M) are in it. Released: commit `388386d` pinned, backup `aa-db-2026-10-21-1923.sql.gz`, migration 0029, 110 tests, `up -d`, nginx. Note: the rejected 0.23.1 (ds trigger, abbreviations, k/M in the reason) had already been committed and built before the rejection landed; it is harmless and stays underneath.

**Also (20:00 UTC): Shipyard 0.24.1** (commit `6c5ac7e` pinned, backup `aa-db-2026-10-21-1946.sql.gz`, no migration, 111 tests): the quote caps ores at **Jita sell** (owner's correction); a **stock take** button writes off every project-goods lot held (the owner: nothing of the buyback inventory exists beyond what is in the projects hangar; the old lots were sold by direct trade without a record), run once today; and **"correction" joins "accidental"** as an ignore reason (server `conf/local.py`, deploy template, code default). The evening's 12 manufacturing jobs (16,615,908: ten at 19:29 of 830,899 each, two at 19:27 of 4,153,459 each) were private builds charged to the corporation; the owner deposited with "correction" in the reason; their 24 journal lines are flagged by id once the hourly read has them (see the end of this entry).

**Figures after all of it (21 Oct, 20:00 UTC):** stock take `WO-261021C` wrote off **522.0 M** at cost (153.9 M of goods held since the baseline and 368.1 M of older lots: Nitrogen Isotopes 228.9, Pyerite 106.2, Tritanium 78.8, Mexallon 56.5, Zero-Point Condensate 22.2, Isogen 18.6, the rest small); goods held now 0; result **+376.5 M** (593.0 before, minus 153.9 written off, minus the 62.5 M "correction manufacturing" deposit that the new pattern now leaves out as it should); gap 0; section 3 net profit so far 47.1 M (the two direct sales in it). Ignored lines: 219, net +8,080,389: the owner's 62,534,212 deposit of the morning also covers carbondnb's ten jobs (8,080,390), but those were paid from the **Director division (7)**, outside the corporation's books, so the master wallet holds 8,080,390 too much. **Owner:** move 8,080,390 ISK from the master wallet to the Director division with "correction" in the reason; the line then leaves the books and the ignored net is 0; the evening's 24 job lines and the 19:03 broker fee are flagged against his 16,642,608 "correction" deposit. Commit `bfb3923` pinned.

**Owner's rule from now on.** Before selling project goods by trade or contract: Finance → Register a direct sale, paste the list, Quote, Register, and put the `DS-XXXX` code in the deposit's reason. Nothing else; no items in the reason.

**Owner has to do by hand.** Nothing for this. Still open: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Next.** Nothing queued.

---

## 2026-10-21 (19:10 UTC) — desktop session → any session

**Runbook / topic:** **Shipyard 0.23.0: direct sales of project goods** (runbook 13 C), and the owner's direct sale of 21 October.

**What happened.** The owner sold nine kinds of project goods by direct trade for 200,415,238 ISK (quote by this session: ores at 95 % of the Reprocessing tab's value capped at Jita sell, White Glaze at Jita buy, Crystalline Isogen-10 and Zero-Point Condensate at Jita buy) and deposited the ISK into the master wallet at 18:34 EVE with the reason "Direct sale buyback goods". The Finance tab counted the cash and still held the goods: the old rule matched lots by the first six letters of the first word after "direct sale", and "buyback" matched nothing. The books never read the corp hangar (no assets scope), so nothing corrects itself when stock leaves it.

**Done.** Shipyard 0.23.0 (commit `fe1cdbe` pinned, backup `aa-db-2026-10-21-1858.sql.gz`, migration 0028, 109 tests): the reason names the items with quantities (`direct sale 2,388 Zero-Point Condensate, 373 Crystalline Isogen-10, ...`; an ore is converted to its minerals as the ledger holds them; a name without a quantity takes every unit held); a deposit that names nothing shows "not matched" on the sheet and is completed in the admin under Shipyard → direct sales (`BookDirectSale`: journal entry id, items) or with `books.direct_sale(entry_id, items)`. Both open cases were recorded that way: entry 26177244778 (today, the nine items: 179.6 M of stock left the books at cost) and the 20 October deposit "Atmospheric Gasses" (typo; recorded as every Atmospheric Gases unit held).

**Owner's rule from now on.** When selling project goods directly, deposit the ISK with a reason like `direct sale 2,388 Zero-Point Condensate, 373 Crystalline Isogen-10` (quantity, then the name, a comma between items; a space after each comma). Ores by their compressed name and units as delivered. Nothing else is needed.

**Owner has to do by hand.** Nothing for this. Still open: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Next.** Nothing queued.

---

## 2026-10-20 (14:40 UTC) — desktop session → any session

**Runbook / topic:** **the accidental corporation sell orders of 2026-10-20 and Shipyard 0.21.0** (runbook 13 C release paragraph).

**What happened.** Six sell orders meant for the owner's own wallet were put up on the corporation (Catherine Frey) between 13:30 and 14:13 EVE: Drake Navy Issue 3, Drekavac 2, Prophecy Navy Issue 7, Caracal Navy Issue 10, Omen Navy Issue 8, Helium Fuel Block 20,000. One Drekavac sold at 13:48 for 147,800,000. The corporation paid 39,847,273 in listing fees (Drake 5,782,104, Drekavac 4,319,408, Prophecy 12,806,257, Caracal 6,194,172, Omen 4,999,759, Helium 5,745,573) and 4,988,250 sales tax on the Drekavac. **Net in the master wallet from the mistake: +102,964,477 ISK.** The owner transfers exactly that from the master wallet (division 1) to his own wallet with a reason that contains the word "accidental"; the corporation is then back at zero and the fees are the owner's own cost. The Drake, Drekavac and Prophecy orders were cancelled; Caracal, Omen and Helium were still open at 14:35 EVE, the owner cancels them. Anything that sells before they are cancelled is a new sale and tax line to flag the same way (a local session: `books.ignore_entries`), and the settlement amount grows by the sale minus its tax.

**Also (2026-10-21, 11:00 UTC): industry jobs paid from the master wallet by mistake, again.** 40 manufacturing jobs at the Raitaru between 10:37 and 10:42 EVE (Tommy McPhee 38,293,042; phosphorescent pony, fluorescent pony and carbondnb 8,080,390 each): **62,534,212 ISK**, the owner deposits that into the master wallet with "accidental" in the reason. The journal copy had 30 of the 40 jobs (60 lines, 54,453,822) at 10:52; they are flagged. **Open for a local session:** flag the 20 lines of the last 10 jobs (carbondnb, 10:41 to 10:42 EVE, 8,080,390) once the hourly read has them (`books.ignore_entries`, reason "accidental industry jobs 2026-10-21"), then check the ignored net is 0 after the deposit. Yesterday's settlement withdrawal of 102,964,477 (14:38 EVE) carried the reason "correction buy orders", without the word "accidental", so it was flagged by id; the 279,919,850 deposit of 16:10 said "accidental correction" and dropped out by itself.

**Also (2026-10-21, 06:10 UTC): Shipyard 0.22.2** (commit `b9fcc3a` pinned, backup `aa-db-2026-10-21-0503.sql.gz`, no migration): the owner wants "My jobs" to be **him and his alts**, not the whole corp: the jobs scope is now every character on the auth account (character ownerships), default for everyone; Whole corp stays for managers. Details in runbook 13 C.

**Also (2026-10-20, 16:05 UTC): Shipyard 0.22.1** (commit `79a81a7` pinned, backup `aa-db-2026-10-20-2057.sql.gz`, no migration): the My business tab opens on **Whole corp** for a manager. The owner saw 518,000 LP where he expected millions: "My jobs" counted only the jobs installed by Catherine Frey, while his production runs on his other characters (phosphorescent pony, fluorescent pony, carbondnb, Tommy McPhee, lkdsfjmqsfd). Whole corp, 90 days: 34,178,000 LP in 1,284 jobs, 7.4 M a week, 29.1 B at the dashboard rates (Federation Navy 9.6 M, Republic Fleet 6.6 M, Caldari Navy 6.0 M, Imperial Navy the rest).

**Also (2026-10-20, 15:25 UTC): industry jobs paid from the corporation wallet by mistake.** All 71 industry jobs started today at the Raitaru (13:48 to 14:09 EVE; 10 blueprint copy jobs by Catherine Frey, 11 fuel block jobs by her, and manufacturing by lkdsfjmqsfd, fluorescent pony, phosphorescent pony, Tommy McPhee and carbondnb) were private builds charged to the corporation: 287,996,120 ISK in job cost, of which 279,919,850 from the master wallet (division 1, 61 jobs) and 8,076,270 from the Director division (7, the ten Caracal Navy Issue jobs of carbondnb). The facility tax part that went to GWON is 3,798,944; the rest went to the SCC. The 122 master-wallet lines (manufacturing, copying, industry_job_tax) are flagged as left out of the books (reason "accidental industry jobs 2026-10-20"). **Owner:** one deposit of 279,919,850 ISK into the master wallet with "accidental" in the reason squares the books (the Director division is outside the books; its 8,076,270 can be deposited there separately or left). Per installer, for collecting: Catherine Frey 182,514,893; lkdsfjmqsfd 35,776,135; fluorescent pony 45,703,162; phosphorescent pony 7,962,830; Tommy McPhee 7,962,830; carbondnb 8,076,270 (division 7).

**Also (2026-10-20, 15:10 UTC): Shipyard 0.22.0** (commit `48c8c71` pinned, backup `aa-db-2026-10-20-1510.sql.gz`, no migration): the My business tab counts the **loyalty points the production used, per faction** and per day, week or month, as the dashboard assumes them (LP per blueprint copy of each ship config), at the dashboard's ISK per LP per faction, next to the character's LP balances from Member Audit and the weeks they last; for tuning the rate the owner pays for LP. Live, 90 days: 518,000 LP in 19 jobs (Federation Navy 198,000, Republic Fleet 160,000, Imperial Navy and Caldari Navy the rest). Details in runbook 13 C.

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

