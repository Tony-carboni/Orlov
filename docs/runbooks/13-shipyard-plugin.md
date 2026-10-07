# Runbook 13 — Shipyard (ship-building dashboard) — private test release

*Prerequisite: Days 0–5 done. Plan in `docs/research/05-industry-dashboard.md`; code in `apps/shipyard/`.*
*Time: ~25 min, of which ~5 min build and ~3 min first data load. Server part is the local session's (handoff); browser part is the owner's.*
*Status: **not released** — only superusers (you) can see the menu entry until the permission is granted to a group.*

**Goal:** `Shipyard` appears in your auth menu with the dashboard of all T1/faction hulls, your facility, Jita prices and the per-ship simulation page. Members can't see it yet.

## Known values

| Item | Value |
|---|---|
| Package | `orlov-shipyard` from this repo, `apps/shipyard`, installed from the GitHub archive of a pinned commit |
| Django app | `shipyard` |
| Default facility (seeded) | Orlov Raitaru — Isikano, rigs: Basic Small / Medium / Large Ship ME I (correct in admin if the real fit differs) |
| Default market (seeded) | Jita IV-4, sales tax base 7.5 %, broker fee base 3 % |
| Permissions | `shipyard \| general \| Can access the Shipyard dashboard`, `… \| Can edit blueprint prices, LP prices and facilities` |
| Beat | `shipyard_refresh_all` every 6 h at :10; `shipyard_refresh_prices_and_stats` hourly at :40 |

## A. Install (server — local session via handoff)

*Done 2026-10-07 13:21–13:29 UTC by the local session: commit `2333032` pinned, backup `aa-db-2026-10-07-1321.sql.gz`, build ok, migration `shipyard.0001_initial` applied, 188 ships (174 active), four refresh steps ok. Order used: requirements → build → settings block → check and migrate from a throwaway container → `up -d`.*

1. Backup (`~/bin/aa-backup.sh`).
2. `conf/requirements.txt`: add the line from `deploy/conf/requirements.txt`, replacing `<commit-sha>` with the full SHA of the current branch head (`git rev-parse HEAD` in the repo clone after pulling).
3. `conf/local.py`: append the "Shipyard" block from `deploy/conf/local.py.append` (from the line `# --- Shipyard` to the end of that block).
4. `docker compose --env-file=.env build`, `up -d`, `restart nginx`.
5. In the gunicorn container: `manage.py check`, `migrate`, `collectstatic --noinput`.
6. `manage.py shipyard_load_ships` (≈190 EVE Ref lookups, ~1 min), then `manage.py shipyard_refresh` (≈190 EVE Ref cost calls + 2 Fuzzwork + 190 ESI history calls, ~3 min).
7. Verify: admin → Shipyard → Refresh runs shows four rows with `ok`; Ships ≈ 190, of which ≈ 170 active.

✅ Done when the left menu shows **Shipyard** for you and the dashboard table has numbers.

## B. First look (browser, you)

1. **Shipyard → My settings**: check the facility card (rigs!), market, click **Load skills from a character** (SSO, read-skills scope), save.
2. **Shipyard → Blueprints & LP**: enter the ISK/LP for the LP stores you use and the blueprint prices you had in the sheet (Vindicator 23 M, Apocalypse Navy 110 M, …). Save.
3. **Dashboard**: compare 5 ships with the sheet. Expected: job cost identical; material cost within a few % (same Jita lowest-sell basis, different minute); profit differs by the broker fee the sheet didn't have (set it to 0 in My settings to compare like for like).
4. Click a ship → move the ME slider, type a blueprint price, Recalculate. The dashboard numbers stay as they were.

## C. Updating the plugin later (local session)
*Update log:*
- *0.1.2, 2026-10-07 14:45 UTC (commit `c9a9206`): **blueprint policy per ship type** (owner's decision, the corp provides blueprints): Base hulls 0 ISK (handed out free); Navy hulls from the corp at the LP-store cost (LP price and tag) **plus 5 % markup** (`SHIPYARD_CORP_BPC_MARKUP` in `local.py`, default 0.05; shown as `LP+5 %`); Pirate (incl. Sisters of EVE), Triglavian and EDENCOM hulls show "public contracts only" instead of a blueprint price and their net profit carries the marker `no BPC` = profit **without** the blueprint. ORE and Other keep the typed price. A typed price on the simulation page overrides the policy. Deployed per section C (no migration); 22 tests.*
- *0.1.1, 2026-10-07 14:10 UTC (commit `48f73d4`): tags are now priced from the market. Each ship can have a **tag type ID** and quantity on the Blueprints & LP page; the price refresh fetches that tag's lowest sell at the default market every hour and the dashboard uses it, divided by the runs of the copy, next to the hand-typed "Extras". The dashboard's type filter became tick buttons: tick any number of types (for example Base and Trig); none ticked shows all; the choice is remembered per browser. Deployed with runbook 13 C: new SHA, build, `check`, 21 unit tests (run against an in-memory SQLite database, because the auth DB user may not create a test database), `migrate shipyard` (0002), `up -d`, `collectstatic`.*
- *Navy cruiser baseline set the same day: ISK/LP Imperial Navy 900, Caldari Navy 900, Federation Navy 850, Republic Fleet 700; the eight navy cruisers (Augoror, Omen, Caracal, Osprey, Exequror, Vexor NI; Scythe, Stabber FI) carry the militia LP-store offer verified in ESI: 18,000 LP, 0 ISK, 1 run, 1 faction crystal tag (True Sansha 17255, Dread Guristas 17244, Shadow Serpentis 17266, Domination 17223). "Blueprints from LP" switched on in the owner's settings. Same day, the other navy hulls (verified in ESI, all 1 run, no tag): destroyers 12,000 LP + 3.5 M ISK, battlecruisers 40,000 LP + 10 M ISK, battleships 100,000 LP + 20 M ISK; the four special-edition battleships (Imperial, Federate, Tribal Issue) are inactive and have no offer. Navy frigates still have no LP offer entered.*


New commits to `apps/shipyard` don't reach the server by themselves. Update = change the SHA in `conf/requirements.txt` to the new commit, rebuild, `up -d`, `restart nginx`, `migrate`, `collectstatic`. Same as Day 4 C4.

## D. Releasing to members (later, your call)

Admin → Groups → `Family Member` → add `shipyard | general | Can access the Shipyard dashboard`. Managers (`Alliance Director`) also get `Can edit blueprint prices…`. Until then only superusers see it. To let one tester in before release: admin → Users → the user → User permissions → add the basic access permission.

## Troubleshooting

- **Menu entry missing** → you're not a superuser on that account, or `collectstatic`/`restart` didn't happen. Superuser = user `tony`.
- **Table empty, "No price data yet"** → `shipyard_refresh` hasn't run or failed; admin → Shipyard → Refresh runs shows the error (usually EVE Ref or Fuzzwork briefly down; rerun).
- **A ship shows ⚠ "missing data"** → a material has no Jita sell order right now (rare) or the EVE Ref call for it failed; it heals on the next refresh.
- **Load skills fails** → the SSO window must be the character whose skills you want; the scope is `esi-skills.read_skills.v1` (ticked on the developer app since Day 0).
- **Numbers look off for a facility** → check its rigs and system in admin → Shipyard → Facilities, then run `shipyard_refresh` (builds are cached per facility).
