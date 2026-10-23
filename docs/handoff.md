# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-23 (05:35 UTC) — desktop session (PC) → any session

**Runbook / topic:** **Shipyard 0.26.2, 0.26.3 and 0.27.0: the goods held are the projects hangar, as raw ore** (runbook 13 C), three owner's rules of this morning (saved in memory as well).

**Owner's rules.** (1) Buyback goods are raw compressed ore sold in bulk: nothing is converted to minerals unless he asks. (2) The goods held from project buybacks are what is physically in the corporation's projects hangar, read from EVE; if it is not there it is not in stock. (3) Stock kept elsewhere (cap boosters, Heavy Water) stays ledger-style as stock batches.

**Done.**
- **0.26.2** (commit `e601e8f`, backup `aa-db-2026-10-23-0515.sql.gz`): ore delivered after the last stock take stays an ore lot at what the project paid (the Kernite project buy is 165, not 180.6 through older mineral lots); the quote costs goods from the lots since the stock take only and skips what earlier registrations sold.
- **0.26.3** (commit `17f1e0e`, backup `aa-db-2026-10-23-0521.sql.gz`): a stock take clears every lot that existed at its moment. The stock take of 21 October had stored the sheet's lines at its journal cut-off, so the deliveries of 21 October 15:25 to 17:27 EVE (about 72 M as minerals) were never written off and reappeared. Goods held now: exactly the 20 items of the owner's list, 130.6 M at project cost, all as ore; gap 0.
- **0.27.0** (commit `04b1df4` pinned, backup `aa-db-2026-10-23-0529.sql.gz`, migration 0032, beat entry `shipyard_refresh_hangar` at :35 appended to `conf/local.py` and `deploy/conf/local.py.append`, 123 tests): the hourly task reads the corporation's assets (scope `esi-assets.read_corporation_assets.v1`) into `HangarItem` rows; the sheet values what is in the hangar at the projects' prices (lots oldest first, excess at the newest lot's price), lists items never bought by a project without counting them, names types the ledger expects but the hangar lacks, and section 2 adds "Hangar count against the ledger" so the sheet still reconciles. Until the first read the goods held follow the ledger and the page says so. Finance tab: **Connect the hangar** (manager; asks for the production scopes plus the assets scope, one token for all) and **Read the hangar now**.

**Owner has to do by hand.** Finance → Connect the hangar, log in with Catherine Frey (CEO; the assets scope needs a Director), accept the scopes. Then say which office and hangar division is the projects hangar (the page lists the divisions the read found) so a local session sets `SHIPYARD_BOOKS_HANGAR_LOCATIONS` and `SHIPYARD_BOOKS_HANGAR_FLAGS`. Still open: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Next (local session, after the login).** Read the hangar now, check the divisions table on the Finance tab with the owner, append the two settings to `conf/local.py` and the deploy template, restart gunicorn and the workers, confirm the goods held equal the hangar and the gap is 0.

---

## 2026-10-23 (05:00 UTC) — desktop session (PC) → any session

**Runbook / topic:** **Shipyard 0.26.0: Register a direct sale values the list six ways** (runbook 13 C), after the owner checked a quote by hand.

**Done.** The owner pasted a 20-line list of project goods (compressed ores, White Glaze, Crystalline Isogen-10, Zero-Point Condensate) and asked for six valuations; the by-hand figures at 04:40 UTC were: quote 156.4 M, project cost 140.8 M (first in first out), Jita buy 154.4 M, Jita sell 164.4 M, 95 % reprocessing with abyssal at Jita buy 160.1 M, the same capped at Jita sell 156.4 M. He wants that table every time, with the margin against the project cost in percent, and sanity checks against odd Jita prices. Released 0.26.0 (commit `c0b7b92` pinned, backup `aa-db-2026-10-23-0444.sql.gz`, no migration, 118 tests): the quote page shows the six valuations with margin in ISK and percent, every line carries Jita buy, Jita sell and the uncapped reprocessing value next to the price used, profit per line as a percentage of cost, and a line is marked when Jita buy is above sell, the spread is over 20 %, the quote is under 85 % of Jita buy, above Jita sell, or the reprocessing value is over 1.25x Jita sell. The rule is unchanged. Live render of the list: three Kernite lines flagged for a Jita spread of 27 to 40 %. **0.26.1** (commit `e8124d8` pinned, backup `aa-db-2026-10-23-0500.sql.gz`, no migration): the lines show **Project buy** (what the projects paid per unit, first in first out) and the profit is against the project cost of every unit sold: units beyond the goods held are priced at the same project buy price instead of counting as free; the registration keeps the lots' cost for the books.

**Owner has to do by hand.** Use Finance → Register a direct sale for the next sale and say if a flag threshold should move. Still open: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Next.** Nothing queued.

---

## 2026-10-22 (15:00 UTC) — desktop session (PC) → any session

**Runbook / topic:** **Shipyard 0.25.1** (runbook 13 C): LP purchase reasons in the owner's spellings, margin cards in sections 3 and 4, the first partial ignore.

**Done.** The owner asked why the sheet showed 1,750 LP while the corporation wallet holds 69,750: the two purchases of today ("57k State protectorate LP" 45.6 M, "11k State Protectorate LP" 8.8 M) did not match the "<number> LP" pattern. Fixed; the sheet now reads 133,000 bought, 63,250 used, **69,750 left (55.8 M at cost)**, the wallet's figure. New cards **Margin on what sold** (sold stock only, sale price against cost, before fees): section 3 **13.1 %** (537.1 M sold against 474.8 M paid to members, market and direct sales), section 4 **10.5 %** (133.7 M against 121.0 M). The 62,534,212 deposit of 21 Oct 10:56 is ignored for 54,453,822 only; the 8,080,390 stays as cash (owner's decision). Result **+366.1 M**, gap 0. Released: backup `aa-db-2026-10-22-1444.sql.gz`, build, 117 tests, `up -d`, nginx.

**Also:** the 9,000,000 deposit "correction industry orders" (22 Oct 13:13) settles ten private manufacturing jobs of 13:10 charged to the master wallet (20 lines, 8,008,380); the lines are flagged and the deposit is ignored for 8,008,380, so 991,620 stays as cash by the owner's rule of 21 October. Ignored lines now 240, net 0; result **+375.1 M**, gap 0. Still open from earlier: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Also (0.25.2, 15:40 UTC):** the owner expected the LP line's Log button to list the corporation wallet's LP change by change with dates; the 0.25.0 log is the member characters' own LP. EVE has no corporation LP route, so the button now opens a page rebuilt from the books (purchases from the journal with EVE's dates, conversions from the stock batches): numbered lines with change and balance after, and the figure the corporation wallet's LP tab should show. Commit `b313603` pinned, backup `aa-db-2026-10-22-1507.sql.gz`, 118 tests.

**Also (runbook 19, 15:15 UTC): the welcome DM.** New cog `orlovbot/cogs/welcome.py` (registered in `orlovbot/auth_hooks.py`, settings `ORLOVBOT_WELCOME` and `ORLOVBOT_WELCOME_CHANNEL_ID` in `conf/local.py`, copy `local.py.pre-welcome`): every member who joins the Discord gets a DM from Orlov auth with the link to #how-to-get-roles and the two-line summary; if their DMs are closed, the same note goes into the channel with a mention. The bot's Members intent was already on (allianceauth-discordbot). Deployed and the cog loads; a test DM with the text was sent to the owner's own account. Not yet seen with a real join: the owner can test with a second account (runbook 19 B).

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
