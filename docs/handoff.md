# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-22 (15:00 UTC) — desktop session (PC) → any session

**Runbook / topic:** **Shipyard 0.25.1** (runbook 13 C): LP purchase reasons in the owner's spellings, margin cards in sections 3 and 4, the first partial ignore.

**Done.** The owner asked why the sheet showed 1,750 LP while the corporation wallet holds 69,750: the two purchases of today ("57k State protectorate LP" 45.6 M, "11k State Protectorate LP" 8.8 M) did not match the "<number> LP" pattern. Fixed; the sheet now reads 133,000 bought, 63,250 used, **69,750 left (55.8 M at cost)**, the wallet's figure. New cards **Margin on what sold** (sold stock only, sale price against cost, before fees): section 3 **13.1 %** (537.1 M sold against 474.8 M paid to members, market and direct sales), section 4 **10.5 %** (133.7 M against 121.0 M). The 62,534,212 deposit of 21 Oct 10:56 is ignored for 54,453,822 only; the 8,080,390 stays as cash (owner's decision). Result **+366.1 M**, gap 0. Released: backup `aa-db-2026-10-22-1444.sql.gz`, build, 117 tests, `up -d`, nginx.

**Also:** the 9,000,000 deposit "correction industry orders" (22 Oct 13:13) settles ten private manufacturing jobs of 13:10 charged to the master wallet (20 lines, 8,008,380); the lines are flagged and the deposit is ignored for 8,008,380, so 991,620 stays as cash by the owner's rule of 21 October. Ignored lines now 240, net 0; result **+375.1 M**, gap 0. Still open from earlier: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Also (0.25.2, 15:40 UTC):** the owner expected the LP line's Log button to list the corporation wallet's LP change by change with dates; the 0.25.0 log is the member characters' own LP. EVE has no corporation LP route, so the button now opens a page rebuilt from the books (purchases from the journal with EVE's dates, conversions from the stock batches): numbered lines with change and balance after, and the figure the corporation wallet's LP tab should show. Commit `b313603` pinned, backup `aa-db-2026-10-22-1507.sql.gz`, 118 tests.

**Next.** Nothing queued.

---

## 2026-10-22 (10:30 UTC) — desktop session (PC) → any session

**Runbook / topic:** **runbook 18, juicy killmails in #juicy-killmails** (owner's request).

**Done.** New channel `#juicy-killmails` under *Member channels* (permissions synced with the category, so members post, react and send GIFs; one overwrite lets the bot's role *Orlov auth* post). New bot cog `orlovbot/cogs/juicy.py`: the kill feed's live reader now hands every killmail in EVE to the other cogs (`zkill_killmail` event, `cogs/killfeed.py`), and the juicy cog posts the ones that meet the owner's rules (supercarriers and titans always; alliance tournament and limited edition hulls always; faction hulls above 20 B; jump freighters above 15 B; freighters, Bowhead, Orca, Porpoise above 8 B; haulers above 10 B; black ops above 12 B; any other non-capital ship above 10 B), reason in the footer, gold embed with the ship render. Thresholds are settings (`ORLOVBOT_JUICY_*_B`, appended to `conf/local.py` and in `deploy/conf/local.py.append`). Released 10:11 UTC: old bot folder kept as `~/backups/orlovbot.pre-juicy-*`, dry run in a fresh bot container (23 rule cases right, real titan and supercarrier losses rendered), bot container restarted, `orlovbot.cogs.juicy` listed, test post of a Nyx loss (killmail 139319386) in the channel at 10:12 UTC. A test post later: set the cache key `orlovbot:juicy:test` to a killmail id.

**Owner has to do by hand.** Look at the channel; say if a rule should move. Still open: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Next.** Nothing queued.

---

## 2026-10-22 (08:30 UTC) — desktop session (PC) → any session

**Runbook / topic:** **Shipyard 0.25.0: the LP log** (runbook 13 C release paragraph). Built in parallel with the other desktop session's 0.23.0 to 0.24.2 of 21 October (direct sales, stock take, partial ignores); rebased on top of them, so the LP log is 0.25.0 with migration 0031.

**Done.** EVE keeps no history of loyalty points, so the plugin keeps its own: the hourly task `shipyard_lp_snapshots` (beat entry at :50, appended to `conf/local.py` and `deploy/conf/local.py.append`) reads every character with a valid token carrying the loyalty scope (Member Audit's registration gives it) and stores a line only when a balance moved: when, character, NPC corporation, change, new balance. A fall that matches a "Payment to LP Store" line in Member Audit's journal is noted with the ISK. Page at /shipyard/lp/log/ (earned and spent per corporation, balance now, chart per day/week/month, the log; "Me and my alts" or, for managers and finance viewers, "Everyone logged"); **Log** button on the Finance tab's Loyalty points line; link from My business. Of the owner's 11 characters, 10 carry the scope; Flapoor Hendrik does not. The log starts with the first reading. **Released:** commit `9bc391e` pinned, backup `aa-db-2026-10-22-0748.sql.gz` (copies `requirements.txt.pre-0.25.0`, `local.py.pre-0.25.0`), migrations 0030 and 0031, all images built, beat entry appended, `up -d`, nginx, 116 tests. First reading by hand at 07:52 EVE: 45 characters read, 365 balances stored (the owner's 10 characters: 53 lines). Note: the other session had pinned 0.24.2 (`bd3b5f6`, migration 0030, the amount on an ignored line) at 20:00 UTC on 21 October but the running containers were still 0.24.1 and 0030 unapplied; this release carries it live.

**Owner has to do by hand.** Register Flapoor Hendrik in Member Audit once if that character's LP matters. Still open: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Next.** Nothing queued.

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

