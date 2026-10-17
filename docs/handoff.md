# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-17 (14:10 UTC) — desktop session → any session

**Runbook / topic:** **Doctrines 0.2.0 and the first doctrine** (runbook 16 D), on the owner's doctrine text file and his fitting export.

**Done.**
- Doctrines 0.2.0 (commit `14ecacc` pinned): a **variant** field on a ship (T1, T2); the doctrine page lists a hull once per role with the cost and loss of each variant, and the opened row has T1 / T2 buttons that switch the fitting shown. Strengths and weaknesses are written one per line as `Keyword - description` and the keyword comes out bold. `DOCTRINES_HOST` is read at call time so tests can override it. 16 tests. Released per runbook 13 C: backup `aa-db-2026-10-17-1353.sql.gz`, `requirements.txt.pre-doctrines-0.2.0` in `~/backups`, build of **all** services (the workers and beat build their own image from the same Dockerfile; building only gunicorn leaves them on the old version), throwaway `check` and `migrate --plan`, migration 0002, collectstatic before `up -d`, `up -d` (the Discord bot is recreated with the rest and came back), nginx. Verified: gunicorn, workers and beat on 0.2.0, 0 errors.
- The doctrine **AB Armor frigs** (category Light & cheap, gameplay Faction warfare) loaded from the shell: 8 hulls, 15 fits converted from the owner's `fittings.xml` (the "Doctrine 1 - <ship> T1/T2 - checked" entries; the export file is cut off at the end but those fits are intact), named "<Hull> T1" / "<Hull> T2", roles DPS (Punisher, Rifter, Incursus), Logi (Inquisitor, Navitas), Tackle (Executioner, Atron), Support (Crucifier, T2 only). All 15 parsed, 75 types resolved, prices read; T1 fits 2.3 to 3.4 M, T2 4.0 to 8.4 M. The strengths and weaknesses are the owner's four and three, paraphrased; description, summary and strategy notes are drafts by the session. No SRP level set. The owner's file says "Easy & Cheap"; the seeded category "Light & cheap" was used.
- Page rendered as the owner (200) and the layout checked in the browser pane.

**Owner has to do by hand**
- Read https://doctrines.orlovfamily.space/doctrines/ab-armor-frigs/ and edit the texts in the admin (https://auth.orlovfamily.space/admin/doctrines/doctrine/): the strategy notes and description are drafts; set SRP levels per ship if wanted; rename the category to "Easy & Cheap" under Categories if preferred.
- Write the landing text (Landing page text) and delete or hide the sample "Example: Rail Harpies".
- Runbook 16 E (browser checks, copy a fit into the game).
- Still open: My business "Connect the jobs" with Catherine Frey; Structure income untick your own payers; send Eemar the CEO roster guide.

### Next — any session
More doctrines: the owner hands over a text file in the same shape (name, type, strengths, weaknesses, roles with ships) plus the fitting export; the converter and loader of this session live in the session scratchpad only, so a new session rewrites them from `apps/doctrines` (store a ship with `fittings.store`, then `prices.refresh`). A management command for that import would save the rewrite.

---

## 2026-10-17 (10:35 UTC) — desktop session → any session

**Runbook / topic:** **runbook 16 A and C, the doctrines site is live** at https://doctrines.orlovfamily.space.

**Done.** The owner added the DNS record and the Nginx Proxy Manager host (A; the tunnel must use the `orlov` alias, noted in the runbook). The desktop session then did C: `local.py.pre-doctrines-host` in `~/backups`, `DOCTRINES_HOST = "doctrines.orlovfamily.space"` in `conf/local.py`, gunicorn, workers and beat restarted. Verified from the server: new host → 302 `/doctrines/` → 302 SSO login with `next=/doctrines/go/`; auth's `/doctrines/` → 302 to the new host; auth's login unchanged; 0 errors. Shipyard untouched at 0.13.3 (`695b655`), Doctrines 0.1.0 (`6495158`).

**Owner has to do by hand**
- Runbook 16 D: write the landing text and the doctrines in auth's admin (https://auth.orlovfamily.space/admin/doctrines/); fittings pasted from the game's Export → To clipboard. Edit or delete the sample doctrine "Example: Rail Harpies".
- Runbook 16 E: the browser checks (private window → the new address → EVE login → landing page; copy a fit; a Family Friend sees "not for you").
- Still open from earlier entries: My business "Connect the jobs" with Catherine Frey; Structure income untick your own payers; send Eemar the CEO roster guide.

### Next — any session
Nothing on the server until the owner has written doctrines. If a doctrine shows "EVE does not know" or a question mark for cost, see the troubleshooting table in runbook 16.

---

## 2026-10-17 (09:25 UTC) — desktop session → any session

**Runbook / topic:** **runbook 16, the doctrines site** (owner's request: doctrines.orlovfamily.space behind auth, landing page with philosophy and tiles in four categories, doctrine pages with ships, Jita cost, net Platinum insurance, SRP level, fitting view with copy-to-clipboard). Built as a new plugin `apps/doctrines/` (0.1.0, commit `6495158`), 13 tests, README in the app.

**Done (server, runbook 16 B).** Backup `aa-db-2026-10-17-0902.sql.gz`; `orlov-doctrines` added to `conf/requirements.txt` pinned to `6495158` (Shipyard pin untouched); Doctrines block appended to `conf/local.py` with `DOCTRINES_HOST = ""` (the host is **switched off** until A and C); build, migration 0001, `doctrines_seed`, collectstatic, `up -d`, nginx; permission `doctrines.basic_access` on the state Family Member, `manage_doctrines` (and read) on the group Alliance Director; insurance table read (570 hulls). Verified on the live stack: anonymous → login, owner 200, Family Friend sent away, admin 200, beat entries `doctrines_refresh_prices` (:35) and `doctrines_refresh_insurance` (05:40) loaded, 0 errors. An inactive sample doctrine "Example: Rail Harpies" with a real fitting proved parsing, ESI type resolution and pricing (cost 37.5 M, net insurance 3.8 M). The address in the request was `.com`; built for `.space` (the alliance domain, where the login cookie works).

**Owner has to do by hand**
- Runbook 16 A: Porkbun A record `doctrines` → 167.99.207.145, and the Nginx Proxy Manager host `doctrines.orlovfamily.space` (copy the shipyards host, new Let's Encrypt certificate). Then say "switch the doctrines host on" to a local session (16 C).
- Runbook 16 D: write the landing text and the doctrines in auth's admin (https://auth.orlovfamily.space/admin/doctrines/); fittings pasted from the game's Export → To clipboard. Until the host is on, the pages live at https://auth.orlovfamily.space/doctrines/.
- Edit or delete the sample doctrine in the admin.

### Next — any session
Runbook 16 C once A is done: set `DOCTRINES_HOST = "doctrines.orlovfamily.space"` in `conf/local.py` (copy first), restart gunicorn and the workers (`up -d` recreates), check from the server: visitor on the new host → 302 `/doctrines/` → 302 SSO login with `next=/doctrines/go/`; auth's `/doctrines/` → 302 to the new host. Shipyard stays at 0.13.3 (`695b655`).

---

## 2026-10-15 (15:40 UTC) — desktop session → any session

**Runbook / topic:** runbook 13 C, Shipyard **0.13.2** (payers left out of the Structure income figures) and **0.13.3** (fuel blocks on My business), on the owner's requests of today.

**Done**
- 0.13.2 (commit `b59b0a3`, migration 0019, backup `aa-db-2026-10-15-1526.sql.gz`): a **Count** checkbox per payer in "Who pays" on the Structure income tab; unticked = that payer's tax is left out of every figure on the page, the ledger keeps the entries, the row stays dimmed with a "left out" badge and can be ticked again. Meant for the owner's own alts and OARMI's jobs, which pay the Raitaru tax to his own structure corp.
- 0.13.3 (commit `695b655` pinned, backup `-1532`): fuel blocks as a product line on My business: charts of blocks sold and produced per period by block, sales ISK per period by type with fuel included, a fuel table by block, a Fuel row in produced-versus-sold. Live: 741,044 blocks sold for 13.6 B since 2026-09-26.
- Both released per runbook 13 C (details there). Tests 86.

**Also (2026-10-16):** `docs/guides/soe-epic-arc-runbook.md` (the other session's file of 2026-10-15, merged with this session's version: one guide now), the owner's in-game runbook for raising Caldari State standing with the Sisters of EVE epic arc (The Blood-Stained Stars, 51 missions, +0.875 of the distance to 10.0 with Social V, no derived changes, every 90 days), with his own numbers (Caldari State −0.27 → ≈ +0.63, broker fee 1.461 % → ≈ 1.434 %, about 130 M/month at the current 490 B of monthly orders) and Penumbra as the next step (needs 5.00 with Caldari State or Expert Distribution).

**Also (2026-10-16):** user `Gizzimo` showed as `[.WAR.]` because their main was the character Gizzimo (Warforged Militants, NC.); their alt BadOmens joined OARMI on 2026-10-15 20:09. On the owner's instruction the main was set to BadOmens from the shell (`profile.main_character`, `assign_state()`); state Family Member, group `corp_OARMI`, Discord nickname `[OARMI] BadOmens` with roles Family Member and `corp_OARMI` (the first Discord push hit auth's rate limiter, the retry a minute later went through, as with Braadslee). Crimson Harvest 2026 (6 Oct–3 Nov): only shooting the Triglavian wormhole guards costs Triglavian standing; the event sites do not.

**Also (2026-10-17):** "update user tommicus" per runbook 04 E: Tommicus Aurilen SWA → OARMI in auth, Family Friend → Family Member, `corp_OARMI`, Discord `[OARMI] Tommicus Aurilen` with Family Member and `corp_OARMI` (verified on the server). The owner first said "atlas": no user, character or Discord member by that name exists in auth.

**Owner has to do by hand**
- Structure income: untick the payers that should not count (your own characters, OARMI if its job tax is your own money moving).
- My business: still **Connect the jobs** with Catherine Frey (0.13.0) so the production charts and the produced columns fill; until then they read 0.

### Next — any session
Nothing queued. Shipyard 0.13.3 on the server (commit `695b655` pinned).

---

## 2026-10-14 (desktop session) — alliance news site, runbook 15

**Done (desktop).** Public page for State-of-the-Union style reports: `site/alliance/` in the repo (Markdown posts, `build.py`, dark template), served by a new `alliance_site` nginx container on the server (`~/aa-docker/alliance-site/`, service appended to `docker-compose.yml`, backup `docker-compose.yml.pre-alliance-site`; 12 containers up). First draft post built and copied; `curl http://alliance_site/` from the proxy container answers 200. Runbook 15 written.

**Also (11:10 UTC):** Shipyard 0.11.0, the **Structure income** tab (runbook 13 C): GWON wallet ledger, income per period and per payer, hourly task; migration 0016 applied, beat entry added, 79 tests, 12 containers up. **Owner:** on https://shipyards.orlovfamily.space/shipyard/income/ press *Connect the wallet* and log in to EVE with Vieze Jonge Pass (GWON's CEO), accept both scopes; then *Read the wallet now*. Done by the owner at 11:15; 0.11.1 fixed the payer corporations and the header badge; ledger 1,122 entries since 2026-09-14, 74 M income in the last 30 days (OARMI 40 M, Ceken 22 M, Max Caulfield 10 M).

**Also (11:30 UTC):** Shipyard 0.12.0, the **Corp projects** tab (runbook 13 C, research 08): OARMI projects snapshotted hourly, payouts per period, contributors; migration 0017, beat entry, 81 tests, 12 containers up. **Owner:** on https://shipyards.orlovfamily.space/shipyard/projects/ press *Connect the projects* and log in to EVE with Catherine Frey, accept the scope; then *Read the projects now*. 0.12.1 fixed the DataTables column-count warning on the empty projects page.

**Naming (owner, 2026-10-14):** the site at alliance.orlovfamily.space is called **the alliance website** from now on. The first post, "State of the Union, October 2026" (full version, written with the owner), is built and copied to the server; the owner writes the in-game mail summary himself and links to https://alliance.orlovfamily.space/2026-10-14-state-of-the-union-october-2026.html.

**Also:** Tavaga (Discord flambo2018) added to the auth group `FC` on 2026-10-14, Discord roles pushed (True).

**Discord (2026-10-14, through the auth bot's token):** `#pings` under Member channels is now read-only for Family Member (view, history, reactions; no posting, threads or mentions) and FC, Corp Director and Alliance Director may post and use @everyone/@here. A second, stray `#pings` outside any category exists; the owner deletes it by hand if unwanted. The owner's new **FCs** category (fc-discussions, fittings, voice4) is hidden from @everyone and Family Member; FC, Corp Director and Alliance Director hold a liberal set there (post, mentions, attachments, threads, manage messages, voice incl. stream, soundboard, move/mute).

**Also (15:35 UTC):** Shipyard **0.13.0, the My business tab** (runbook 13 C): the chosen character's wallet, ships sold per dashboard category and hull class with four Chart.js charts, production metrics from OARMI's industry jobs (hourly copy, migration 0018, beat entry at :20), produced-versus-sold per category. Live: 1,204 ships sold for 94.5 B since 2026-09-26, wallet 96.95 B. **Owner:** on https://shipyards.orlovfamily.space/shipyard/business/ press *Connect the jobs* and log in to EVE with Catherine Frey (OARMI's CEO, so Factory Manager), accept the scope; then *Read the jobs now*; the production charts fill from the last 90 days of corp jobs. Tests 85.

**Also (afternoon):** 0.13.1, 7 and 14 day ranges on My business (the range applied to the by-ship table all along; the data is younger than 30 days). Server pinned at `5dcf4f1`, 85 tests.

**Moon board (2026-10-16):** restyled like the structure board and shows the auto-pop time (runbook 09); deployed to the bot, backup `moons.py.pre-autopop`.

**Owner does by hand:** runbook 15 A (Porkbun A record `alliance` to 167.99.207.145) and C (Nginx Proxy Manager proxy host `alliance.orlovfamily.space` to http://alliance_site:80 with a Let's Encrypt certificate). Then write the real post in `site/alliance/posts/` and say "publish the alliance news" to a local session (15 D).

**Also since the last entry:** Republic Fleet LP value 725 ISK/LP (2026-10-13); Shipyard 0.10.3 (Blueprint column includes the cruiser tag); guide `docs/guides/corp-roles.md`.
