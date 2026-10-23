# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-23 (07:45 UTC) — desktop session (PC) → any session

**Runbook / topic:** **Shipyard 0.27.2 and 0.27.3: all-time cards in section 3, and a fix to how a direct sale of ore takes its lots** (runbook 13 C).

**Done.**
- **0.27.2** (commit `47079ff`, backup `aa-db-2026-10-23-0714.sql.gz`, no migration): section 3 has a second row of cards, "since the first project": paid to members since the first payout the books know (4 October 2026, 13 members, 1,237.6 M), net profit on what sold and the margin on sold stock, across every reporting period; the PDF has the same as one line. Direct sales of earlier periods keep taking their lots once a new period opens (they were only matched when inside the period).
- **0.27.3** (commit `965827e` pinned, no migration, 126 tests): found while checking the new cards. Since 0.26.2 an ore delivered after the stock take has a lot of its own, and a direct sale took only from that lot: the 21 October sale (18:34, before the stock take) found nothing for its seven ore lines, the stock take wrote those goods off instead (605.9 M), and the sale showed 95.4 M cost and a 37 % margin. An ore now leaves from its own lots first and the rest through its minerals. Live: the sale costs 179.5 M with every line matched, the write-off 521.8 M (the stock take page says 522.0 M), margin on what sold 13.1 %, all-time net profit 46.9 M on 537.1 M sold, gap 0.

- **0.27.4** (commit `ffad25b` pinned, no migration): the owner chose Week and saw the report's numbers in the period row. Week and Month start before the books begin (18 October), so they count from the baseline until 25 October and 17 November (0.27.1); the subtitle now says so, the period cards are titled "this period", the all-time row ignores the menu. Day differs already.

**Owner has to do by hand.** Look at the new row on Finance → section 3. Still open: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep, test the welcome DM with a real join.

**Next.** Nothing queued.

---

## 2026-10-23 (05:35 UTC) — desktop session (PC) → any session

**Runbook / topic:** **Shipyard 0.26.2, 0.26.3 and 0.27.0: the goods held are the projects hangar, as raw ore** (runbook 13 C), three owner's rules of this morning (saved in memory as well).

**Owner's rules.** (1) Buyback goods are raw compressed ore sold in bulk: nothing is converted to minerals unless he asks. (2) The goods held from project buybacks are what is physically in the corporation's projects hangar, read from EVE; if it is not there it is not in stock. (3) Stock kept elsewhere (cap boosters, Heavy Water) stays ledger-style as stock batches.

**Done.**
- **0.26.2** (commit `e601e8f`, backup `aa-db-2026-10-23-0515.sql.gz`): ore delivered after the last stock take stays an ore lot at what the project paid (the Kernite project buy is 165, not 180.6 through older mineral lots); the quote costs goods from the lots since the stock take only and skips what earlier registrations sold.
- **0.26.3** (commit `17f1e0e`, backup `aa-db-2026-10-23-0521.sql.gz`): a stock take clears every lot that existed at its moment. The stock take of 21 October had stored the sheet's lines at its journal cut-off, so the deliveries of 21 October 15:25 to 17:27 EVE (about 72 M as minerals) were never written off and reappeared. Goods held now: exactly the 20 items of the owner's list, 130.6 M at project cost, all as ore; gap 0.
- **0.27.0** (commit `04b1df4` pinned, backup `aa-db-2026-10-23-0529.sql.gz`, migration 0032, beat entry `shipyard_refresh_hangar` at :35 appended to `conf/local.py` and `deploy/conf/local.py.append`, 123 tests): the hourly task reads the corporation's assets (scope `esi-assets.read_corporation_assets.v1`) into `HangarItem` rows; the sheet values what is in the hangar at the projects' prices (lots oldest first, excess at the newest lot's price), lists items never bought by a project without counting them, names types the ledger expects but the hangar lacks, and section 2 adds "Hangar count against the ledger" so the sheet still reconciles. Until the first read the goods held follow the ledger and the page says so. Finance tab: **Connect the hangar** (manager; asks for the production scopes plus the assets scope, one token for all) and **Read the hangar now**.

**Owner has to do by hand.** Finance → Connect the hangar, log in with Catherine Frey (CEO; the assets scope needs a Director), accept the scopes. Then say which office and hangar division is the projects hangar (the page lists the divisions the read found) so a local session sets `SHIPYARD_BOOKS_HANGAR_LOCATIONS` and `SHIPYARD_BOOKS_HANGAR_FLAGS`. Still open: DigitalOcean weekly backups check, the stray #pings, roster tokens for GB44 and 1E3, which of the seven project graphs to keep.

**Also (05:55 UTC): the hangar is connected and pinned.** The owner logged in with Catherine Frey and read the hangar; the first count took every corp hangar division everywhere (29 lines, 9.4 B, the owner's own mineral stock included). The projects hangar is **structure 1055529310484, hangar division 2** (40 item types): `SHIPYARD_BOOKS_HANGAR_LOCATIONS = [1055529310484]`, `SHIPYARD_BOOKS_HANGAR_FLAGS = ["CorpSAG2"]` appended to `conf/local.py` and the deploy template, app containers restarted. Goods held now: 18 lines, 109.7 M at project cost, gap 0, result +405.7 M. Not in that hangar although bought by projects: 600 Zero-Point Condensate and 36 Crystalline Isogen-10 (they sit in structure 1055543898857, division 1, with the owner's own 14,931 ZPC and 13,156 CI-10), so the sheet counts them out and shows "Hangar count against the ledger" −21.0 M; the owner decides whether to move them into the projects hangar. 22 types in the projects hangar were never bought by a project (moon ores, Compressed Scordite and the like) and are listed, not counted.

**Also (06:10 UTC): Shipyard 0.27.1** (commit `fc4ed62` pinned, backup `aa-db-2026-10-23-0604.sql.gz`, no migration, 125 tests): a **period menu** at the top of the Finance tab, Since: Last alliance report / Day / Week / Month; Day, Week and Month open a period on the fly (the position 24 hours, 7 or 30 days ago becomes the opening, nothing stored; the PDF follows `?period=`); a start before the budget baseline of 18 October falls back to the baseline, so Week and Month equal the report until 25 October and 17 November. **Structure income** is one line in its own category in section 2 (the 77.0 M of 18 October and the 59.9 M of 23 October, 136.9 M together; the transfer rule is `raitaru|structure income`). Also refreshed from ESI today on the owner's request: leadplayer (now OARMI) and Kevin Choseph (now OARMI, Family Member).

**Next.** Nothing queued.

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
