# Ship-building dashboard for members — plan

*Research 2026-10-07. Goal: turn the owner's Excel "dashboard" (EVE Excel add-in) into a members-only web page with a live list of T1 hulls (base, navy, pirate, Trig, ORE, Deathless) ranked by build profit, a per-ship breakdown, and a top-10 post in Discord. Low threshold: a new member should be able to open it, pick a ship, and know what to buy and what they'll make. Not built yet; this is the plan.*

## 1. What the sheet does today

One tab per faction, one block per ship; the "Main dashboard" tab links them and sorts by profit. Per ship:

| Step | Sheet formula (EVE add-in) | Value today (Vindicator) |
|---|---|---|
| Type ID | `INVENTORYSEARCH(name)` | 17740 |
| Sell price | `MARKET_ORDERS_STATS(The Forge, type, Jita 4-4)` → sell **min** | 999.9 M |
| Volume | `MARKET_HISTORY(The Forge, type, 7 d)` volume ÷ 7 | 7.6 / day |
| Bill of materials | `BLUEPRINT(type)` → manufacturing materials, qty × **0.99** (Raitaru hull bonus), rounded up | 11 lines |
| Input cost | Σ qty × Jita min sell | 818 M |
| Adjusted cost (EIV) | Σ qty × CCP adjusted price | 235 M |
| Job cost | EIV × (0.04 SCC + 0.97 × system index) — index from `INDUSTRYINDEX(Isikano)` = 3.75 % | 18.0 M |
| Sales tax | 4.81 % × sell | 48 M |
| Blueprint price | typed by hand (BPC cost) | 23 M |
| Tag price | typed by hand (navy/pirate LP-store tags, `Variables` tab) | 0 |
| Profit | sell − (input + BPC + tags + job cost + sales tax) | 92.7 M (9.3 %) |

Fixed assumptions in `Variables`: Raitaru, hull ME bonus 1 %, T1 rig 2.98 %, job-cost multiplier 0.97, SCC 4 %, facility tax 0. Build system Isikano (0.68 high-sec).

Known gaps worth fixing in the web version: no **broker fee** on the sale (1–3 % depending on skills/standings; at 1 B hulls that's 10–30 M, bigger than the job cost); "min sell" can be a one-unit outlier (use the 5 % percentile sell instead); sales-tax rate is a constant (depends on Accounting skill); no build time, skill requirements or number of job slots, which is exactly what a new member needs to know.

## 2. Where live data can come from (instead of the Excel add-in)

All free, all public, no EVE login needed for any of it:

| Source | Gives | Notes |
|---|---|---|
| **EVE Ref industry cost API** `api.everef.net/v1/industry/cost` | the whole calculation in one GET: materials with qty and cost, EIV, job cost incl. SCC and system index, facility tax, build time, for a given product, ME/TE, structure, rigs, system | **Verified:** for Vindicator in Isikano / Raitaru / T1 ME rig it returns job cost 17,985,640 — identical to the sheet. Material prices default to CCP average; selectable. Rate-limit-friendly: one call per ship per refresh. |
| **Fuzzwork market aggregates** `market.fuzzwork.co.uk/aggregates/?region=10000002&types=…` | per type: min/max/median/weighted avg/5 % percentile for buy and sell in The Forge, many types per call | the Jita "sell min" and the better "sell percentile" in one request for all 100 hulls + all materials |
| **ESI** (CCP, no auth) | `/markets/10000002/history/?type_id=` (daily volume), `/industry/systems/` (cost indices), `/markets/prices/` (adjusted prices) | volume per ship needs one call per ship; cached 1 h; fine for ~100 types |
| **EVE Ref reference data** `ref-data.everef.net/blueprints/{id}`, `/types/{id}` | static data: blueprint materials, skills required, groups, meta | replaces the SDE download; already used by EVE Ref's own cost API |
| EVE SDE (CCP static dump, via Fuzzwork) | same static data as a local SQLite | only if we want zero external dependencies |

Ready-made sites that already do most of this (eveindustry.app, Fuzzwork blueprint calculator, Ravworks, "EvE Blueprint") are good, but generic: they don't say *which* ship a new Orlov member should build, don't bake in our structure and system, and need the member to know what to type. Linking them from the detail page as "check it yourself" is still useful.

Alliance Auth plugins checked: `aa-industry` (0.2.2) only lists industry jobs; `aa-blueprints` (3.1.0) lists owned blueprints and handles copy requests. Nothing existing does profit ranking. `aa-blueprints` becomes interesting later (which BPCs the corp can hand out).

## 3. Where the app runs — three options

| | A. Alliance Auth plugin (page inside auth.orlovfamily.space) | B. Own container at `industry.orlovfamily.space` | C. Static site rebuilt by a nightly job |
|---|---|---|---|
| Login / who sees it | free: `Family Member` permission, same login as everything else | needs its own EVE SSO or an auth-token check, or be public | public, or hidden behind an unguessable URL |
| Hosting work | none beyond what we did for Member Audit (package in the custom image, migrate) | new DNS record, proxy host, cert, backup line | DNS + proxy host serving a folder |
| Data refresh | Celery beat task, same pattern as moonmining | own scheduler | cron |
| Discord top-10 | same webhook pattern as aa-structures | own code | cron + curl |
| Effort to first version | ~2 days | ~3 days | ~1.5 days |
| Fits "very low threshold" | yes: members already log in to auth for Discord | yes if public | yes, nothing to log in to |

**Recommendation: A, an Alliance Auth plugin** (working name `orlov-shipyard`, menu entry "Shipyard"). Reasons: the numbers are corp business, not for the public; every member already has an auth login; permissions, Celery, Discord webhooks, backups and the update procedure all exist; and the page can later use the member's own data (their skills from Member Audit, their blueprints from aa-blueprints) to personalise "what should *I* build". Option C stays the fallback if you decide the list may be public.

## 4. Design

**Data pipeline (Celery, every 2 h; cheap: ~100 EVE Ref calls, 2 Fuzzwork calls, ~100 ESI history calls):**
1. Ship list = all `Ship` category types in the T1 hull groups we care about (frigate … battleship, mining barges, industrials optional), filtered by meta group: Tech I, Faction/Navy, Pirate, Triglavian, Deathless, ORE. Maintained as a config list with overrides, seeded from the sheet's 104 ships.
2. For each ship: EVE Ref cost (materials, EIV, job cost, time) with our structure/rig/system; Fuzzwork Jita sell percentile for the hull and every material; ESI 7-day volume.
3. Add the hand-maintained parts in an admin table: BPC price per ship, LP/tag cost per ship, facility tax, sales tax %, broker fee %.
4. Store one snapshot row per ship per run (so trends and "price moved" flags are possible).

**Page 1 — ranking.** Table with filters (size, category, "beginner" toggle) and columns: ship, category, size, sell price, input cost, job cost, taxes, **net profit**, margin %, daily Jita volume, build time, skills needed. Sort by profit by default. A "beginner" toggle hides ships that need tags/LP, special skills, or sell < 1 per day.

**Page 2 — ship detail.** Bill of materials with qty, unit price, line cost and volume (m³ to haul); cost waterfall (materials → job cost → BPC → tags → broker → sales tax → profit); build time; required skills; where to buy (Jita) and sell; copy-paste shopping list in multibuy format; links to EVE Ref / eveindustry.app for the "check it yourself" crowd.

**Discord.** Weekly post (Monday 18:00) to `#market-industry` via webhook: "Top 10 ships to build this week" as an embed, one line per ship with profit, margin, volume, plus a link to the page. Optional later: `/shipyard <ship>` slash command via the AA discordbot.

**Guidance for new members.** A fixed intro block on page 1: how to get the BPC (corp hands them out via aa-blueprints requests later), where to build (our Raitaru in Isikano), ME assumptions, how to sell. Three starter picks flagged by hand ("good first builds") until the beginner score is trusted.

## 5. Phases

| Phase | Deliverable | Effort |
|---|---|---|
| 1 | Plugin skeleton, ship list, pipeline, ranking page; numbers verified against the sheet for 5 ships | 1 day |
| 2 | Detail page, shopping list, admin table for BPC/tag prices | ½ day |
| 3 | Weekly Discord top-10, permissions, member intro text, runbook 08 | ½ day |
| 4 (later) | Beginner score from skills (Member Audit), personal "what can I build", aa-blueprints integration | open |

Development happens in a separate repo (`Tony-carboni/orlov-shipyard`, pip-installable like the other apps), deployed through the same custom-image requirements line. The local session can run it against the live auth; the cloud session writes the code.

## 6. Decisions needed from the owner

1. Members-only inside auth (recommended) or public page?
2. Price basis for materials and hulls: Jita sell min (as the sheet) or Jita sell 5 % percentile (safer)? Recommend percentile.
3. Structure assumptions to bake in: Raitaru in Isikano with T1 ME rig and 0 % facility tax — still correct? Any second build location?
4. Sales tax 4.81 % and broker fee: what values for a typical member (Accounting / Broker Relations level)?
5. Which categories in v1: the sheet's set (base, navy, pirate, Trig, Deathless, ORE)? Industrials and mining barges too?
6. Tag/LP pricing: keep hand-maintained per ship, or price tags from Jita automatically where a tag item exists?
7. Discord: `#market-industry`, weekly Monday 18:00, top 10 overall or top 3 per size class?

## Sources
- EVE Ref industry cost API: https://docs.everef.net/api/industry-cost (verified call 2026-10-07)
- Fuzzwork market aggregates: https://market.fuzzwork.co.uk/aggregates/
- ESI: https://esi.evetech.net/ui/ (markets history, industry systems, markets prices)
- EVE Ref reference data: https://ref-data.everef.net/
- EVE Excel add-in function docs: https://forums.eveonline.com/t/add-in-function-documentation/417665
- eveindustry.app: https://forums.eveonline.com/t/web-tool-eveindustry-app/506842
- aa-industry / aa-blueprints on PyPI (checked 2026-10-07)
