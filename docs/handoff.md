# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-17 (18:20 UTC) — desktop session → any session

**Runbook / topic:** **Doctrines 0.2.6, the landing page text, the backups** (runbooks 16 and 04 A).

**Done.**
- **Landing page text** (auth admin → Doctrines → Landing page text, one `SiteText` row, set from the shell): title "How we Fly", the owner's two paragraphs (wording as given, including "strenghts"), then a lead line and five bullets that explain the roles a pilot can fill (DPS, Logistics, Tackle, Support with EWAR, boosts and scouts, FC) instead of the four fleet-type bullets; each explanation starts with a capital letter (owner's request after seeing the tags).
- **Doctrines 0.2.6** (commit `12fd77b` pinned): a list line written as `Keyword: explanation` renders the keyword as an uppercase tag with the role's icon and colour and the explanation beside it (tag column left, text right, stacked on a phone); the same five colours mark the ratio chips on the card and the role headers of the ships table (`ROLE_KEYS` / `role_key()` in `services/fittings.py`, `split_keyword` / `tag_html` in the template tags, `data-role` attributes, colour tokens `--dc-role-*` in the stylesheet). Design rules applied: one colour per role everywhere, icon and name next to the colour, light tints on the navy for at least 4.5:1 contrast, the explanation kept in the body colour. Released per runbook 13 C: backup `aa-db-2026-10-17-1801.sql.gz`, `requirements.txt.pre-doctrines-0.2.6` in `~/backups`, build of all services, `check`, no migration, 20 tests green on the image (one older test now accepts the hashed static name of the fitting-wheel script; it could never pass against the live settings), collectstatic, `up -d`, nginx. Verified as tony: five tags on the landing page, chips and role rows carry `data-role`, the stylesheet is served by nginx with the new rules, 0 gunicorn errors.
- **Backup diagnostic** on the owner's request. Found: the nightly job (cron 03:30, `~/bin/aa-backup.sh`) runs every night and its dump is sound (gzip ok, 265 tables incl. the doctrines ones), 14 days kept; the config tarball held `.env`, `conf/` and the compose file. Gaps: Nginx Proxy Manager's proxy hosts and the seven Let's Encrypt certificates (Docker volumes, nowhere in a backup), the bot's code, the alliance site, the backup script and the crontab (all small, mostly in git), and above all no copy off the server. Done: the script now also archives those (`aa-proxy-<stamp>.tgz` and a fuller `aa-config-<stamp>.tgz`; old copy `~/backups/aa-backup.sh.pre-proxy-2026-10-17`; source of truth `deploy/bin/aa-backup.sh`), ran once (18:15 UTC, all three files verified), and the three files were copied to the PC at `C:\Users\Toon Budeners\OrlovBackups\2026-10-17\` (outside the repo; holds `.env`). Not covered on purpose: `grafana-data` (dashboards only), redis (cache), the static volume (rebuilt by collectstatic), `~/shipyard-dev` (scratch).

**Also (2026-10-17, 18:35 UTC):** the Punisher T1 showed 192.2 M because the only Heat Sink I sell order at Jita 4-4 at the 18:04 read was a 189.9 M one (meta-0 module, two orders in the station); a refresh by hand brought it to 2.52 M. Proposed, not built: read The Forge's 5 % percentile next to the station minimum and fall back to it when the station figure is more than twice as high, with a "thin market" marker; or swap the module for a Compact variant in the fit. The corporation import file `docs/doctrines/armor-ab-frigs.xml` (15 fits, names `<Doctrine> - <Hull> - <T1/T2>`) was validated and copied to this PC's EVE fittings folder, which is `OneDrive\Dokumente\EVEittings` here. **Doctrines 0.2.7** (commit `7d65e4b` pinned, released per runbook 13 C, 20 tests): the ratio chips are labelled "Target composition · per N pilots" with the explanation on hover.

**Owner still has to do by hand.**
- Check in the DigitalOcean panel whether the weekly Droplet backups are enabled (runbook 04 B1); that is the "server died" layer and cannot be seen from the server. If not, enable them.
- Repeat the copy to the PC now and then (runbook 04 B2), or ask the local session for it.
- Still open from before: "Connect the projects" with Catherine Frey on the Shipyard projects tab; delete the stray top-level #pings; roster tokens for GB44 and 1E3.

**Next.** Nothing queued. Any session: `git pull` and read this entry.

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

**Also (2026-10-17, 18:00 UTC):** the doctrines landing page text (auth admin → Doctrines → Landing page text, the one `SiteText` row) was replaced from the shell on the owner's instruction: title "How we Fly", his two paragraphs (wording kept as given, including "strenghts"), and, instead of the four fleet-type bullets, five bullets explaining the roles a pilot can fill: DPS, Logistics, Tackle, Support (EWAR, boosts, scouts) and FC, matching the role names on the doctrine cards. Verified rendered at doctrines.orlovfamily.space as tony: three paragraphs, five bullets, old bullets gone. Nothing in the code changed; the text lives in the database only.

## 2026-10-17 (14:35 UTC) — desktop session → any session

**Runbook / topic:** **Doctrines 0.2.1 → 0.2.5** on the owner's requests while he reviewed the first doctrine page; all released per runbook 13 C (backups `aa-db-2026-10-17-1414`, `-1424`, `-1428`; `requirements.txt.pre-doctrines-0.2.x` in `~/backups`; build of all services each time; migration 0003 in 0.2.1; collectstatic before `up -d`). Live now: 0.2.5 (see below), 0 errors.

**Done**
- 0.2.1: **SRP percent** per doctrine (`srp_percent`, migration 0003) shown as a yellow tag on the tile and the page card and taken off the final cost; **role headers** in the ships table (DPS, Logi, Tackle, Support, with an icon and the hull count) with the hulls indented under them, the Role column gone; the T1 / T2 choice as **Bootstrap tabs** (label, "lower skills" / "full skills", the fit's cost) joined to the panel; the explanatory paragraph above the table removed (the column headers carry it on hover).
- 0.2.2: the **fitting wheel**: an opened fit draws the game's fitting window with the `shipfit` web component (npm `shipfit` 1.0.0, MIT, 396 KB, self-hosted in `static/doctrines/vendor/` with a licence file; item data bundled from 2021, only EVE's image server at runtime; its GitHub repository is gone, the npm package remains). This is what the owner remembered from other alliances' doctrine pages. Looked at and not taken: EVEShip.fit's React components (React plus self-hosted data files behind CORS) and quiescens' eve-ui (a list, jQuery, unmaintained).
- 0.2.5: the **target ratio of the roles** on the card (`composition`, one `Role: number` per line, migration 0005), chips with the role icons; AB Armor frigs set to DPS 6, Logistics 2, Tackle 1, Support 1. Live: commit `4647fc3` pinned, 19 tests.
- 0.2.4: the owner changed his mind: the table is **Cost** (one decimal on millions) **and SRP as a percentage** only; a ship's own *SRP percent* overrides the doctrine's (migration 0004), the two logi hulls set to 100 %. Net insurance and the final cost are still computed, not shown. Live: commit `740cd9a` pinned, 18 tests.
- 0.2.3: the table read **Cost, SRP, Net insurance, Final cost** (cost minus SRP minus net insurance) with the Shipyard reprocessing rounding (`isk_auto`: millions with three decimals, 100 k and up whole).
- Content of **AB Armor frigs** set from the owner's texts (summary, strengths, weaknesses, strategy notes), the description cleared (the card shows the name and the summary only), SRP 50 %.

**Owner has to do by hand**
- Import the corporation fits: `Armor AB Frigs.xml` is in `Documents/EVE/fittings/` (copy in `docs/doctrines/`), fitting window → Import & Export → Import from file, then save each as a corporation fit. Next doctrines: hand over a text file in the same shape plus the fitting export (re-export it; the current `fittings.xml` is cut off at the end).
- Landing text; delete or hide "Example: Rail Harpies"; runbook 16 E.
- Still open: My business "Connect the jobs" with Catherine Frey; Structure income untick your own payers; send Eemar the CEO roster guide.

### Next — any session
A management command `doctrines_import` (text file + fitting export → doctrine with T1/T2 ships) would replace the session-scratchpad converter used for the first doctrine. The table shows two lines per hull (T1 and T2); if the owner wants one line, show the T2 figures in the row and keep T1 in the tabs.

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

