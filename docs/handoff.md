# Session handoff

Shared notebook between the **cloud session** and the **local session** (rule in `CLAUDE.md`, "Session handoff"). Newest entry on top. Each session pulls and reads the top entry before resuming, and writes a new entry, commits and pushes before the owner switches. No secrets, no fenced blocks.

---

## 2026-10-09 (08:00 UTC) — desktop session → any session

**Runbook / topic:** runbook 13 C, Shipyard **0.8.5 released** (Scrapmetal table easier to read; the owner's request from the screenshot of 2026-10-09).

**Done**
- Confirmed for the owner: **Value** = Σ floor(quantity × yield) × Jita lowest sell × (1 − tax), yield from the character's Scrapmetal Processing (V for the owner), tax 0 at the Isikano Raitaru.
- Commit `ce24e15` (version 0.8.5): ISK columns in whole thousands (exact amount on hover); **Gives** column = each mineral's share of the value with its in-game icon, the three largest with a percentage, the rest dimmed icons, names still searchable; **column widths** draggable at the header's right edge, remembered per browser (localStorage), double-click resets. Tests 66 in a throwaway container against the working copy (`~/shipyard-dev`), live page render 200 on the standalone host, the drag tested in the desktop app's browser.
- Released per runbook 13 C: backup `aa-db-2026-10-09-0740.sql.gz`, `requirements.txt.pre-0.8.5` in `~/backups`, `ce24e15` pinned, build, throwaway `check` (no migration), `up -d` (all healthy), nginx restarted, collectstatic (124 copied); the served CSS/JS contain the new code, 0 gunicorn errors.
- Fixed on the PC: the SSH key `~/.ssh/orlov-claude` had Windows line endings and no trailing newline (OpenSSH: "invalid format"); rewritten with LF and a final newline, read-only ACL restored, backup `orlov-claude.crlf-backup` beside it. Git identity set for this repository only (same name and e-mail as earlier commits). The first push needed a one-time GitHub sign-in in the Git Credential Manager window; the credential is stored now.
- Python 3.12.10 installed for the owner's user via winget (the owner asked); on the user PATH for new terminals.

**Open (owner)**
- Look at the Scrapmetal tab on `shipyards.orlovfamily.space`: whole-thousand ISK, icons in Gives, drag a column edge. Say if the share percentages should be shown for more or fewer than three minerals, or if the icons should be bigger.
- From the previous entry: group names polished (say if any should change); more modules via admin → Shipyard → Scrap items or a list for the local session.

### Next — any session
Nothing queued. Pick up whatever the owner asks next; the Shipyard is at 0.8.5 on the server (commit `ce24e15` pinned).

---

## 2026-10-08 (15:45 UTC) — laptop session → any session

**Done**
- "update user braadslee": SAK (NPC corp) → OARMI/ORLOV, Family Friend → Family Member, `corp_OARMI`, Discord roles and nickname synced (runbook 04 E; the first Discord push hit auth's rate limiter, the retry a minute later went through).
- **Shipyard 0.8.0: the Scrapmetal tab** (owner's part B of the reprocessing request; details in runbook 13 C and research 07 §6). Working copy tested in a throwaway container (66 tests); migration 0010 applied to the live DB from there; catalog imported (66 modules, all priced, volumes read); owner's skills reloaded (Scrapmetal Processing V); released per runbook 13 C (commit `15a30ad` pinned, backup `aa-db-2026-10-08-1526.sql.gz`, `requirements.txt.pre-0.8.0` and `local.py.pre-0.8.0` in `~/backups`, beat entry `shipyard_refresh_scrap_catalog`).
- Other members' Scrapmetal Processing level arrives with their next daily skill refresh (or when they click a character); until then the tab uses the default V and says so.

- **0.8.1/0.8.2 (commit `5a4d295`):** the owner wants the table to mirror the in-game market tree for quick scanning: groups in his exact in-game folder order, a header row per group, modules indented and in the client's alphabetical order. Done and released (same procedure, backup `aa-db-2026-10-08-1604.sql.gz`); `group_order` of the stored rows updated from the constants.

**0.8.3 (desktop session, 16:30 UTC):** Sell % column removed from the Scrapmetal table; favourable switch and colouring follow Buy %. **0.8.4:** Metal Scraps and Reinforced Metal Scraps as the group "Metal scraps" below the thermal hardeners.

**Open (owner)**
- Look at the Scrapmetal tab: group names were polished (say if any should change); the v2 sheet's extra groups "cap booster" and "fr-x heavy" were not in the list and are not in the app. More modules: admin → Shipyard → Scrap items (type id + group), or hand the local session a list.


---

## 2026-10-08 (13:50 UTC) — desktop session → any session

**Done (desktop).** The GB44 one-off below is closed: both mains showed alliance ORLOV in auth, backup `aa-db-2026-10-08-1347.sql.gz` taken, GB44 removed from the `Family Member` state's corporations (now OARMI, GWON), both users re-evaluated and still `Family Member`; `docs/design/membership.md` change log updated. Shipyard today went 0.3.4 → 0.7.4 (contract prices, own prices, Refresh button, Reprocessing tab with Buy % / Sell %, Vol/day, Depth, grades, moon rarity R4–R64 and area filters); every release is in runbook 13 C. Access to the Shipyard is the owner only for now. Open: the owner may correct the ore-area table (`DEFAULT_AREAS` in services/reprocessing.py, overrides via `SHIPYARD_ORE_AREAS`); a part B of the reprocessing request may follow.

---

## 2026-10-08 (12:47 UTC) — scheduled cloud session → local session

**Runbook / topic:** one-off removal of Go Browns [GB44] from the state "Family Member" (see `docs/design/membership.md`, change log).

**What was done.** Checked EVE's public API on 2026-10-08 at 12:47 UTC. The corporation Go Browns (corporation_id 98845722) shows alliance_id 99015337. That alliance has the ticker ORLOV (The Orlov Family). So EVE now shows GB44 inside ORLOV and the one-off in the state is no longer needed.

**Owner has to do by hand:** nothing.

### Next - local session

Prompt for the local session: remove corporation GB44 (corporation_id 98845722) from the member_corporations of the State named "Family Member" via the Django shell in the allianceauth_gunicorn container. Announce the write first, run one step at a time, show the result. Before the removal, take a backup with ~/bin/aa-backup.sh. Never print .env contents.

1. Read-only first: list the users Masterxxx and MrFreshy_Valterus with their state and their main character's alliance as auth sees it. Check the State "Family Member": its member_alliances and member_corporations.
2. If auth still shows no alliance (or not ORLOV) for their main characters, run the eveonline character update for those characters (or wait for the periodic update) and check again. Only continue once both mains show alliance ORLOV in auth.
3. Announce, then remove GB44 from member_corporations of the State "Family Member" in the Django shell. Show the resulting member_corporations.
4. Confirm that Masterxxx and MrFreshy_Valterus still have state Family Member through the alliance rule (re-check the state, trigger a state update if needed). If either lost the state, add GB44 back at once and report.
5. Add a line with today's date to the change log in docs/design/membership.md, commit and push to claude/orlov-alliance-auth, and write the next handoff entry.

---

## 2026-10-07 (18:00 UTC) — laptop session → desktop session (owner continues tomorrow)

**State of play in one paragraph.** The Shipyard is at **0.3.0** on the server (commit `07f5edb` pinned), with three releases today from this session: 0.1.7 (standings in the broker fee), 0.2.0 (the own front door, switched off), 0.3.0 (My industry page, own blueprints in the numbers, corp/alliance scopes). The front door `shipyards.orlovfamily.space` is **built but closed**: it waits for the owner's DNS record and proxy host (runbook 14 A), then one settings flip (14 C). Everything below is in the repo; the server matches `deploy/`.

### What the owner decided today (laptop session)
- **Front door:** Family Member **and** Family Friend may use it; characters grant **everything** (the 33 Member Audit scopes); it runs on the existing server (headroom checked).
- **My industry:** a full dashboard of jobs and assets; a Family Member sees **only their own characters**, a **Corp Director** everyone in their corp, an **Alliance Director** everyone in the alliance.
- **Pirate / Trig / EDENCOM blueprints:** keep showing the profit **without** the blueprint ("public contracts only", marker `no BPC`); do **not** subtract a typed price. Reason: contract prices move too fast to maintain; the owner checked that sheet profit + sheet BPC = app profit without BPC (Vindicator: 52.4 M + 23 M ≈ 71.4 M after the small timing and tax differences) and is satisfied. Members judge a copy's price themselves with the blueprint-cost field on the ship page. Wording wish for the next release: the label should read **"only on public contracts"** (today: "public contracts only"); no rebuild for that alone.
- **Standings:** yes, factor them in (done in 0.1.7). Sales tax is not affected by standings, only the broker fee.

### Server state after this session
- Containers: all 11 up, Shipyard 0.3.0 installed, site 200, bot found its three boards after each `up -d`, 0 errors in the logs.
- `conf/local.py` is 244 lines. Appended today, in this order: the "Shipyards front door" block with `SHIPYARD_STANDALONE_HOST = ""` (door closed), `MIDDLEWARE += ["shipyard.middleware.StandaloneHostMiddleware"]`, `SESSION_COOKIE_DOMAIN`/`CSRF_COOKIE_DOMAIN = ".orlovfamily.space"`, `CSRF_TRUSTED_ORIGINS += ["https://shipyards.orlovfamily.space"]`; then the beat entry `shipyard_refresh_industry` (crontab minute 5,35). `deploy/conf/local.py.append` has the same blocks (with the real host name in the template).
- Migrations applied: shipyard 0003 (market owners, standings) and 0004 (industry tables, two permissions). No pending migration.
- Permissions: `shipyard.basic_access` on the **states** Family Member (11 accounts) and Family Friend (1); `view_corp_industry` on group Corp Director (3 members); `view_alliance_industry` on group Alliance Director (tony). The runbook-13-D group grants from earlier are superseded by the state grants.
- Owner's settings: skills and 83 standings of Catherine Frey stored; broker fee at Jita 1.461 %.
- Industry data already read for tony's 10 characters (first read happened in the dry run); the half-hourly task keeps it fresh for everyone who opens the page once.
- Backups in `~/backups`: `aa-db-2026-10-07-1638/1701/1744.sql.gz`, `requirements.txt.pre-0.1.7/0.2.0/0.3.0`, `local.py.pre-0.2.0/0.3.0`, `local.py.pre-reinforce-hour` etc. from the bot work.
- Discord: System Messages Channel moved to `#public-chat` on 2026-10-06; otherwise untouched today.

### Code map of what changed today (apps/shipyard/shipyard)
- `middleware.py` — host routing for the front door (`StandaloneHostMiddleware`): pass-through prefixes, SSO bounce `/shipyard/go/`, 403 page `no_access.html`, redirect of auth's `/shipyard/…` to the standalone host. Reads `app_settings.standalone_host()` per request.
- `services/characters.py` — `full_scopes()` (Member Audit's `Character.esi_scopes()` or `constants.FULL_SCOPES`), `token_for()`, `register_in_memberaudit()`, `load_character()` (skills + standings, clears manual overrides), `ensure_fresh()` (daily), `choices()` for the picker.
- `services/industry.py` — `sync_user()` / `sync_all()` / `sync_character()` (jobs + slot skills every 30 min, blueprints and assets every 6 h; assets kept for `relevant_type_ids()` only and rolled up with `root_location()`), name caches `ensure_type_names()` (into `MaterialType`) and `ensure_location_names()` (`LocationName`; structures via the character's token, unknown ones retried after a day), `owned_blueprints()`, `allowed_scopes()` / `visible_syncs()`, `overview(user, scope)` (a finished job EVE still calls "active" counts as ready).
- `services/board.py` — `dashboard_rows()` uses the member's best own blueprint (ME/TE) through `simulate_build()` for at most 25 ships per render; `BoardRow.owned_bp`.
- `services/esi.py` — `_authed()`, `_authed_pages()` (X-Pages, cap 20), `character_skill_levels()`, `character_industry_jobs()`, `character_blueprints()`, `character_assets()`, `structure_info()`, `character_standings()`.
- `services/pricing.py` — broker fee with standings (`SHIPYARD_BROKER_FACTION_STANDING_PER_POINT` 0.0003, `…CORP…` 0.0002).
- `views.py` — `_context()` picks the frame; `use_character()` (POST from the picker; SSO once with all scopes, session key `shipyard_sso_pending`; falls back to the character the member actually logged in with), `go()`, `industry_view()` (GET `?scope=own|corp|alliance`, POST = refresh own characters), `ship_detail()` starts the simulation at the own blueprint's ME/TE. `load_skills` and the manual skill/tax inputs are gone.
- `models.py` — `MarketLocation.owner_corporation_id/owner_faction_id`, `UserSettings.standings/standings_fetched_at/standing_with()`, `CharacterSync`, `IndustryJob`, `CharacterBlueprint`, `CharacterAsset`, `LocationName`; `General` permissions ×4.
- `tasks.py` — `refresh_industry` (beat :05/:35). `constants.py` — `FULL_SCOPES`, `ACTIVITIES`, `SLOT_SKILLS`. `templatetags` — `shipyard_logout_url`, `remaining`.
- Templates — `frame_standalone.html` / `frame_auth.html` (base.html extends the `frame` variable), `settings.html` (character picker), `industry.html` (scope buttons, strip, jobs, blueprints, stock), `no_access.html`; dashboard badge "your BPO ME10"; detail header shows the own blueprint.
- Tests: 47 (`test_pricing.py`, `test_board.py`, `test_frontdoor.py`, `test_industry.py`).

### Useful patterns learned today (for the desktop session)
- **Test and dry-run the working copy before building:** `tar` `apps/shipyard` to `~/shipyard-dev` on the server (strip CR), then `docker compose run --rm --no-deps -T -v ~/shipyard-dev/apps/shipyard:/dev/shipyard:ro --entrypoint sh allianceauth_gunicorn -c '... PYTHONPATH=/dev/shipyard ...'`: `manage.py check`, the unit tests with the SQLite settings file in `/tmp`, `makemigrations --check`, and a Django test `Client` with `force_login` and `HTTP_HOST` for live page renders. Migrations can be applied from there too (additive ones are safe before the build).
- Release = runbook 13 C: backup → copy `requirements.txt` → `sed` the SHA → build → throwaway checks → migrate → `up -d` → `restart nginx` → `collectstatic` → verify → docs.
- Python patch scripts for docs must normalise CRLF before matching and be re-runnable; run them with `python -X utf8` from a file (heredocs mangled the en dashes and `\U` in Windows paths).
- The sheet: `OneDrive/EVE/ships dashboard v3.2.xlsx` on the laptop; copy it out of OneDrive before reading with openpyxl.

### Open items, in order
1. ~~Owner (runbook 14 A)~~ **done 2026-10-08** (DNS record and proxy host with certificate; the new host served auth's dashboard).
2. ~~Local session (14 C)~~ **done 2026-10-08 by the desktop session:** `SHIPYARD_STANDALONE_HOST = "shipyards.orlovfamily.space"` set, containers restarted, redirect chain verified (visitor → `/shipyard/` → SSO login → EVE; auth's `/shipyard/` → new host). **Open: the owner's browser check, runbook 14 D.** Original text of this item: set `SHIPYARD_STANDALONE_HOST = "shipyards.orlovfamily.space"` in `conf/local.py` (sed on the existing line), `docker compose restart allianceauth_gunicorn allianceauth_worker allianceauth_worker_services allianceauth_beat`, then from the server: `curl -sI https://shipyards.orlovfamily.space/` → 302 to `https://auth.orlovfamily.space/sso/login?next=/shipyard/go/`, and `curl -sI https://auth.orlovfamily.space/shipyard/` → 302 to the new host. Then the owner does 14 D.
3. **Owner checks:** `#structure-board`/`#moon-board`/`#zkillboard`/`#jf-gank-board` looks; the 3 Nov reinforcement date in game; Go Browns' alliance join (then remove GB44 from the Family Member state's corporations); profile names for the structure board; "refresh the founders" once new Family Members are in.
4. **Shipyard 0.3.1–0.3.3 released 2026-10-08 by the desktop session** (search box, no toggles, dark theme, swappable facility card, settings = character only, markup 10 % + manager override set to 0 for tony, Consortium hulls off, Isikano tax 0.1 %; details in runbook 13 C). **0.3.4 released 2026-10-07 20:15 UTC by the desktop session:** Perseverance set to public contracts only via a per-ship policy table (`BPC_POLICY_BY_NAME`), no migration, 48 tests. **0.4.0 released 2026-10-08 08:20 UTC by the desktop session:** right-click a Blueprint cell on the dashboard to type your own price for the copy; it replaces the corp's figure in your own numbers (also on the ship page), marked `yours`, until cleared. This supersedes the earlier "do not subtract a typed price" for pirate hulls: a price the member types for themselves is subtracted, the corp-wide policy is unchanged. Migration 0006 applied, 49 tests. **0.4.1 released 2026-10-08 08:40 UTC:** "public contracts only" and "not priced yet" are gone, the cell reads "Price not known" until a value is entered (owner's wording). **0.5.0 released 2026-10-08 08:50 UTC:** Pirate/Trig/EDENCOM blueprint prices come from public contracts (EVE Ref snapshot, hourly beat entry `shipyard_refresh_contract_prices`, migration 0007, 55 tests; owner's rule = average per run of the cheapest five runs on offer in The Forge, outliers above 3× the cheapest ignored; details in runbook 13 C and research doc 06). **0.5.1:** Jita 4-4 contracts only (`SHIPYARD_CONTRACT_STATIONS`); outlier guard kept on the owner's say-so. **0.5.2:** manager Refresh button on the dashboard (queues prices, volumes, contract prices; 5-minute cooldown). Pack contracts count under the rule (a 7-copy Vedmak pack at 39 M made the figure 5.57 M while singles sat at 6.78 M); the owner looked, bought the pack and keeps the rule as is. **0.6.0:** the contract figure moved to its own "Contracts" column, information only; the Blueprint column (own set price, else corp figure, else Price not known) is the only thing in the numbers. **0.6.1:** the Contracts column shows the cheapest per-run price listed and the hover names the contract (ID, issuer, price, copies/runs, ME/TE, title, expiry). **0.7.0 released 2026-10-08 12:00 UTC:** Reprocessing tab (compressed ore and ice at the owner's T2 Tatara in Sobaseki, 80.9 % yield, 2 % tax, price points 90–100 %; research doc 07; migration 0008; weekly catalog beat entry). **0.7.1:** Buy % (Jita highest buy order ÷ value) is the leading ratio, Sell % kept. The owner's request had an "A) Main dashboard" heading, so a part B may follow. The owner cleared his own Vedmak/Drekavac/Rodiva prices himself; 750 k on the 12 base battleships remains. Later on 2026-10-08 the desktop session loaded 25 pirate/Trig prices from the owner's sheet `ships dashboard v3.2.xlsx` (OneDrive/EVE, Main dashboard column I) as his own prices; Vedmak, Drekavac and Kikimora he had set himself again. Not in the sheet: Alligator, Khizriel, Cenotaph, Tholos, Damavik, Thunderchild, Skybreaker, Stormbringer, Squall. **Access narrowed 2026-10-08 (owner's wish, 'no family members yet'):** `shipyard.basic_access` removed from the states Family Member and Family Friend and granted to the user `tony` only; a member now gets the 403 page on the front door and no Shipyard menu entry. The group grants `view_corp_industry` (Corp Director) and `view_alliance_industry` (Alliance Director) stay but are inert without basic access. To reopen: put `basic_access` back on the two states (runbook 13 D). Note for the shell: AA's `State.permissions.remove(obj)` raises a TypeError, use `.remove(obj.pk)`. Owner's own-price rows: 750 k per run on the 12 base battleships (set by the desktop session on request), plus Vedmak, Drekavac and Rodiva typed by the owner; own prices win over contract figures. **Next Shipyard release, when there is a reason:** ~~label "only on public contracts"~~ (moot since 0.4.1); ~~navy frigate LP offers~~ (entered 2026-10-08 by the desktop session: 12 navy frigates, 4,000 LP + 2 M ISK, verified in ESI, data only); front-door phase 3 ideas the owner may raise after using phase 2 (for example corp hangar stock, which needs corp roles and the structures token).
5. **Housekeeping:** `~/shipyard-dev` on the server is a scratch copy and can be removed; `tasks.py refresh_industry` logs a `RefreshRun` row "industry" every half hour (admin → Shipyard → Refresh runs).


---
