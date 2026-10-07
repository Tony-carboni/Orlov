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
| Preset public stations (2026-10-07, owner) | Four public Raitarus in Piekura by The Zero-Complaints Logistics Division, 2 % tax, rigs from their in-game bios: *FP Big ship Construction* (Basic Large Ship ME II + TE I, Basic Capital Component ME II), *FP - Fuel, Ammo, Equipemeny* (ammo, equipment, structure rigs; no ship bonus), *FP T1-T2 Small Ships & Drones* (Advanced + Basic Small Ship ME I, Drone ME I), *FP T1-T2-T3 Medium Ship & Comp.* (Advanced Component ME II, Advanced Medium Ship ME II, Basic Medium Ship ME I). Members pick them under My settings → Facility. Each active facility adds ~175 EVE Ref calls to the 6-hourly build refresh |
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
3. **Dashboard**: compare 5 ships with the sheet. Expected: job cost identical; material cost within a few % (same Jita lowest-sell basis, different minute); taxes within a tenth of a percent (the sheet uses a flat 4.81 %, the app computes sales tax from Accounting and the broker fee from Broker Relations and standings). **Pirate, Triglavian and EDENCOM hulls and base battleships show a higher profit than the sheet** because the blueprint policy leaves their blueprint out ("public contracts only", marker `no BPC`); the Vindicator check of 2026-10-07: sheet 52.4 M with a 23 M blueprint, app 71.4 M without it, 48.4 M with 23 M typed in the simulation.
4. Click a ship → move the ME slider, type a blueprint price, Recalculate. The dashboard numbers stay as they were.

## C. Updating the plugin later (local session)

*Releases 0.3.1 to 0.3.3, 2026-10-08 (commit `6f04bf2` pinned): search box on the dashboard (every word must match somewhere in the row); the two toggles (missing data, only profitable) are gone; dark navy theme (Bootstrap dark mode tinted via CSS variables in `shipyard.css`); the facility card shows the structure's render and a Swap button that opens a picker of every active facility (POST `shipyard:set_facility`); My settings is the character picker only (market = the corp default, skills from the character, facility via the card); LP pricing always on; the two Consortium Issue hulls inactive; markup 10 % (`SHIPYARD_CORP_BPC_MARKUP` default 0.10) with a per-member override only managers see on My settings (`UserSettings.bpc_markup`, migration 0005; the owner's is 0, his copies come from his own stash); Isikano facility tax 0.1 % and builds refreshed. Tests 48. Lessons: view tests with the test `Client` need a main character on the user (`AuthUtils.add_main_character_2`), otherwise Alliance Auth's URL wrapper bounces to `/dashboard/`; `handler404/403` in `conf/urls.py` hide errors behind that same redirect, so debug with `DEBUG=True` in a throwaway process.*

*Release 0.3.4, 2026-10-07 (commit `1c8b610` pinned): per-ship blueprint policy exceptions (`constants.BPC_POLICY_BY_NAME`, checked before the type and hull rules); the Perseverance (ORE destroyer) is "public contracts only" like the pirate hulls, so its blueprint is left out of the cost and the net value carries the `no BPC` marker. No migration. Tests 48.*
- *0.3.0, 2026-10-07 17:50 UTC (commit `07f5edb`): **My industry** page: jobs, blueprints and stock of the member's characters from ESI; own blueprints' ME/TE used on the dashboard and ship pages; scopes own / corp / alliance behind two new permissions on the director groups; background task `shipyard_refresh_industry` (beat :05 and :35). Migration 0004 (five tables, two permissions). 47 tests.*
- *0.2.0, 2026-10-07 17:05 UTC (commit `7fe6752`): **the Shipyard's own front door** (runbook 14, plan in research 06). Middleware for a second hostname, standalone page frame, character picker with the full Member Audit scope set (one SSO prompt per character, registers it in Member Audit), skills and standings refreshed from ESI daily, manual skill levels and tax overrides gone. Released per section C with the front door **switched off** (`SHIPYARD_STANDALONE_HOST = ""`) until the owner has done runbook 14 A; the cookie-domain and CSRF settings are already in place. Access permission moved to the states `Family Member` and `Family Friend` (runbook 14 B). No migration. 37 tests.*
- *0.1.7, 2026-10-07 16:45 UTC (commit `24725dc`): **standings lower the broker fee.** Each market location now records the NPC corporation and faction that own the station (Jita 4-4: Caldari Navy 1000035 / Caldari State 500001, filled in by migration 0003). *Load skills from a character* also reads that character's unmodified NPC standings (scope `esi-characters.read_standings.v1`, already on the developer app via Member Audit) and the broker fee becomes 3 % − 0.3 pp × Broker Relations − 0.03 pp × faction standing − 0.02 pp × corporation standing, as in the game (EVE University wiki, Aug 2026). Sales tax is unchanged: standings never affect it, only Accounting does. My settings shows the standings in use. Released per section C: backup `aa-db-2026-10-07-1638.sql.gz`, build, throwaway container (`check` clean, 25 tests OK, plan), `migrate shipyard` (0003), `up -d`, nginx, `collectstatic`. Members see the effect after clicking *Load skills from a character* once more; the owner's standings were filled in from the server (broker fee 1.5 % → 1.461 %).*
- *0.1.6, 2026-10-07 (commit `6f2c491`): hull group **Industrial** replaces "Hauler" (haulers incl. Noctis, plus inventory group 941 for the **Porpoise**; the Orca comes along inactive, switch it on in the admin if wanted); barges stay a separate group (owner's decision). The hull filter is multi-select like the type filter. The `no BPC` marker also shows on the simulation panel before the first Recalculate. After the deploy: `shipyard_load_ships --no-seed` (renames the hull on existing rows and adds the new ships) and `shipyard_refresh`.*
- *0.1.5, 2026-10-07 (commit `414f9b3`): **base battleships are "public contracts only"** (owner: not newbro ships; by then members source blueprints on the Jita market). The policy is now looked up by type and hull (`constants.bpc_policy(category, hull_size)`, exceptions in `BPC_POLICY_BY_HULL`). Base frigates to battlecruisers stay free.*
- *0.1.3 and 0.1.4, 2026-10-07 ~15:00 UTC (commit `3c84742`): the blueprint column shows the value only (the `LP+5 %` marker is gone; the markup is still inside the number and inside the net profit); a free blueprint reads "Free for corp members", a typed price that is still 0 reads "not priced yet". Same on the detail page and in the simulation.*
- *0.1.2, 2026-10-07 14:45 UTC (commit `c9a9206`): **blueprint policy per ship type** (owner's decision, the corp provides blueprints): Base hulls 0 ISK (handed out free); Navy hulls from the corp at the LP-store cost (LP price and tag) **plus 5 % markup** (`SHIPYARD_CORP_BPC_MARKUP` in `local.py`, default 0.05; shown as `LP+5 %`); Pirate (incl. Sisters of EVE), Triglavian and EDENCOM hulls show "public contracts only" instead of a blueprint price and their net profit carries the marker `no BPC` = profit **without** the blueprint. ORE and Other keep the typed price. A typed price on the simulation page overrides the policy. Deployed per section C (no migration); 22 tests.*
- *0.1.1, 2026-10-07 14:10 UTC (commit `48f73d4`): tags are now priced from the market. Each ship can have a **tag type ID** and quantity on the Blueprints & LP page; the price refresh fetches that tag's lowest sell at the default market every hour and the dashboard uses it, divided by the runs of the copy, next to the hand-typed "Extras". The dashboard's type filter became tick buttons: tick any number of types (for example Base and Trig); none ticked shows all; the choice is remembered per browser. Deployed with runbook 13 C: new SHA, build, `check`, 21 unit tests (run against an in-memory SQLite database, because the auth DB user may not create a test database), `migrate shipyard` (0002), `up -d`, `collectstatic`.*
- *Navy cruiser baseline set the same day: ISK/LP Imperial Navy 900, Caldari Navy 900, Federation Navy 850, Republic Fleet 700; the eight navy cruisers (Augoror, Omen, Caracal, Osprey, Exequror, Vexor NI; Scythe, Stabber FI) carry the militia LP-store offer verified in ESI: 18,000 LP, 0 ISK, 1 run, 1 faction crystal tag (True Sansha 17255, Dread Guristas 17244, Shadow Serpentis 17266, Domination 17223). "Blueprints from LP" switched on in the owner's settings. Same day, the other navy hulls (verified in ESI, all 1 run, no tag): destroyers 12,000 LP + 3.5 M ISK, battlecruisers 40,000 LP + 10 M ISK, battleships 100,000 LP + 20 M ISK; the four special-edition battleships (Imperial, Federate, Tribal Issue) are inactive and have no offer. Navy frigates added 2026-10-08: all 12 (the 8 Navy/Fleet Issue hulls plus Slicer, Hookbill, Comet, Firetail) carry the militia offer 4,000 LP + 2 M ISK, 1 run, no tag, verified in ESI; the 5 % markup applies through the Navy policy.*


New commits to `apps/shipyard` don't reach the server by themselves. Update = change the SHA in `conf/requirements.txt` to the new commit, rebuild, `up -d`, `restart nginx`, `migrate`, `collectstatic`. Same as Day 4 C4.

## D. Releasing to members (later, your call)

Admin → Groups → `Family Member` → add `shipyard | general | Can access the Shipyard dashboard`. Managers (`Alliance Director`) also get `Can edit blueprint prices…`. Until then only superusers see it. To let one tester in before release: admin → Users → the user → User permissions → add the basic access permission.

## Troubleshooting

- **Menu entry missing** → you're not a superuser on that account, or `collectstatic`/`restart` didn't happen. Superuser = user `tony`.
- **Table empty, "No price data yet"** → `shipyard_refresh` hasn't run or failed; admin → Shipyard → Refresh runs shows the error (usually EVE Ref or Fuzzwork briefly down; rerun).
- **A ship shows ⚠ "missing data"** → a material has no Jita sell order right now (rare) or the EVE Ref call for it failed; it heals on the next refresh.
- **Load skills fails** → the SSO window must be the character whose skills you want; the scopes are `esi-skills.read_skills.v1` and `esi-characters.read_standings.v1` (both on the developer app).
- **Broker fee is not what the market window shows** → standings only count after *Load skills from a character* has been clicked since 0.1.7; the market must have its owner corporation and faction set (admin → Shipyard → Market locations). The fee uses unmodified standings, as the game does.
- **Numbers look off for a facility** → check its rigs and system in admin → Shipyard → Facilities, then run `shipyard_refresh` (builds are cached per facility).
