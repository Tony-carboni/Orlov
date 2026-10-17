# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

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

---

## 2026-10-14 (07:30 UTC) — desktop session → any session

**Runbook / topic:** alliance roster coverage, **runbook 15** (corp roster token for CEOs and directors) and **Shipyard 0.10.4** (every scope at the front door), on the owner's request.

**Findings.** EVE: 43 characters in 3 corps (OARMI 30 → 31 during the day, GB44 11, 1E3 2). Auth: 38 registered on 22 accounts, all Family Member. Missing by name (read through Catherine Frey's and Masterxxx's membership-scope tokens): OARMI Goedweer2, Goedweer3, Goedweer4, Goedweer5 (alts of Goedweer1, surely) and Miguel Stevens; GB44 complete; 1E3 one of two, unnamed because Eemar's token has only the basic scope. Hamu (asked about on 2026-10-11) is user `Hamu`, character Hamu 978861931, CAS at the time, OARMI since; Family Friend then, Family Member now; Discord roles were already right.

**Done**
- Permissions: `Corp Director` += corputils *add_corpstats*, *view_corp_corpstats*; `Alliance Director` += those and *view_alliance_corpstats*. Nobody but the superuser had them, so the old CEO guide's "any member can add the Corp Stats token" was wrong in practice.
- `docs/runbooks/15-corp-roster-token.md`: for CEOs/directors, browser only (add page `/corpstats/add/`, one scope, where the lists show, Update button, troubleshooting) and the executor's section (Corp Director group). CEO onboarding guide points to it; CLAUDE.md lists it; membership design change log updated.
- Corp Stats exists for OARMI only (token Catherine Frey, refreshed hourly at :00).
- **Shipyard 0.10.4 released** (commit `184182b` pinned, backup `aa-db-2026-10-14-0945.sql.gz`): owner's rule "scopes as wide as can be": the front door now asks a character for every scope EVE offers (73 = Member Audit's 33 + ESI's 72 + publicData, write scopes included; `SHIPYARD_REQUEST_ALL_SCOPES`, `SHIPYARD_EXTRA_SCOPES`). Tokens are still looked up with the 33, so nobody has to log in again now; the wider set comes with the next login. Member Audit's own Add-character button still asks for its 33 and cannot be widened. Runbook 15 therefore starts with "register the character at the front door"; runbook 14 known values and the member guide (shortcut) updated. Tests 77. Details in runbook 13 C.

**Owner has to do by hand**
- Send Eemar (and Masterxxx for GB44 if you want their roster in auth too) **`docs/guides/corp-ceo-roster-token.md`**, the CEO-facing version via the auth portal (Member Audit registration, 33 scopes, then the Corp Stats add page reuses the token); Eemar is in `Corp Director` already. Note: through auth a character gets Member Audit's 33 scopes, the 73-scope login exists only at the Shipyard front door (Member Audit's button cannot be widened); an auth-side "register with every scope" page is possible if the owner wants the wide set through auth too.
- Nudge Goedweer1 to add Goedweer2–5 to their account, and Miguel Stevens to auth.

### Next — any session
Nothing queued. Shipyard 0.10.4 (commit `184182b` pinned), kill feed with live R2Z2 feed, structure board without fuel pings (2026-10-11).
