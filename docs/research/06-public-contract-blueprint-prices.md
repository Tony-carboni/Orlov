# Research: automatic blueprint prices from public contracts

*2026-10-08, desktop session. Question from the owner: can the Shipyard pull public contract data from EVE and update the pirate (and Triglavian, EDENCOM, ORE, base battleship) blueprint prices by itself, instead of "Price not known"?*

**Short answer: yes.** Public contracts are open data. Two routes exist, and the practical one is a ready-made snapshot that EVE Ref publishes twice an hour, which the server can read with one small download per refresh. Nothing needs a login or a scope.

## 1. What EVE exposes

ESI has three public (no token) endpoints, verified live on 2026-10-08:

| Endpoint | What it gives | Cache | Size |
|---|---|---|---|
| `GET /contracts/public/{region_id}/` | every public contract in a region: id, type (item_exchange, auction, courier), price, title, dates, start location, issuer | 30 min | The Forge 35 pages of 1,000 contracts (about 35,000 open); Domain 4 pages |
| `GET /contracts/public/items/{contract_id}/` | the items of one contract: type_id, quantity, is_included, and for blueprints `is_blueprint_copy`, `runs`, `material_efficiency`, `time_efficiency` | 1 h | one call per contract |
| `GET /contracts/public/bids/{contract_id}/` | bids on an auction | 5 min | not needed |

The contract list carries only the free-text title ("Bellicose BPC 5x10/20"), so to know what is inside a contract you have to call the items endpoint for it. Titles are not reliable for matching; the type IDs in the items are.

Of the 1,000 contracts on The Forge's first page, 997 were item exchanges and 77 had "BPC" in the title.

## 2. Route A: read ESI directly

Poll the region list every 30 minutes, call the items endpoint once for every contract we have not seen before (contract IDs never change, so items are fetched once and cached for the life of the contract), match the items against our blueprint type IDs.

- First run: about 35,000 item calls for The Forge alone (ESI tolerates it, spread over an hour or two, but it is a lot of traffic for 38 ships).
- Every later run: only new contracts, a few thousand a day.
- Needs its own bookkeeping (seen contract IDs, expiry, retries, error-limit handling).

Workable, but heavier than it needs to be.

## 3. Route B: EVE Ref's public contract snapshots (recommended)

EVE Ref already does route A for the whole game and publishes the result:

- `https://data.everef.net/public-contracts/public-contracts-latest.v2.tar.bz2`, about 6 MB, refreshed at :00 and :30 every hour (file seen at 08:01 UTC on 2026-10-08), with a `history/` folder of older snapshots.
- Inside: `contracts.csv` (all regions, with EVE Ref's added `region_id`, `system_id`, `station_id`), `contract_items.csv` (`contract_id`, `type_id`, `quantity`, `is_included`, `is_blueprint_copy`, `runs`, `material_efficiency`, `time_efficiency`), plus files for mutated items and bids we do not need.
- Documented at `https://docs.everef.net/datasets/public-contracts.html`; the scraper is open source.

The Shipyard already depends on EVE Ref for build costs (`services/everef.py`), so this adds no new kind of dependency, only a new URL. One download and one pass over two CSV files per refresh; no ESI calls at all.

Risk: if EVE Ref stops publishing, the prices go stale. The dashboard should show the snapshot time and fall back to "Price not known" when the data is older than, say, a day. Route A remains the fallback plan.

## 4. How a price would be derived

For each ship whose policy is "public" (27 pirate, 6 Triglavian, 4 EDENCOM, the Perseverance, base battleships), take its `blueprint_type_id` and look at contracts where:

1. `type` is `item_exchange` (auctions have no fixed price), `price` > 0;
2. the contract contains that blueprint as a copy (`is_blueprint_copy`), `is_included` true;
3. the contract contains nothing else that is included (single-item contracts only, so bundles and "BPC + hull" packs do not distort the price);
4. the region is one we accept: The Forge first; optionally all high-sec regions with the region name shown.

Price per run = `price / (runs × quantity)`. Then per ship:

- **lowest per-run price** among the matching contracts, and the **second lowest** (the number to use when only one contract exists at a silly price);
- **median** per-run price and the **count** of contracts, as a confidence signal;
- the best contract's ME, TE, runs, station and expiry, for the tooltip.

Suggested rule for the dashboard figure: the lowest per-run price when at least two contracts agree within a factor of two, otherwise the median; "Price not known" when fewer than one contract matches. The exact rule is cheap to change once we see real data.

## 5. Things to watch

- **ME and TE differ between copies.** A ME 0 copy costs more to build with than a ME 10 one. The per-run price should be shown next to the ME/TE of the copy it came from; a later step could feed that ME into the material cost the way the member's own blueprints already do.
- **Scams and outliers.** Contracts priced in billions by mistake, or copies with 1 run at a fair-looking total. The per-run calculation and the second-lowest rule handle most of it; the count makes the rest visible.
- **Bundles.** Rule 3 above drops them. Later, bundles of N identical copies can be accepted (quantity > 1 of the same type is already fine).
- **Location.** A cheap copy in a null-sec station is not cheap for us. Start with The Forge and show the station name.
- **Freshness.** Contracts live up to two weeks; the snapshot is half-hourly. An hourly refresh on the server is plenty.
- **Member's own price wins.** The right-click price (0.4.0) stays on top of the automatic figure, so members can still override.

## 6. What it would take in the Shipyard

- A model for the result (one row per ship: lowest, second lowest, median, count, best contract's ME/TE/runs/station/expiry, snapshot time), or fields on `ShipConfig`.
- A task `refresh_contract_prices` (hourly beat entry): download the archive to a temporary directory, read the two CSVs, match, store; log counts.
- Pricing: a new blueprint source "contract" between the policy's "public" and the member's "own": the value shows with a small marker, the tooltip carries count, ME/TE, runs, station, snapshot time; the `no BPC` marker goes away because the blueprint is in the cost again.
- Detail page: the same figure as the simulation's starting point.
- Tests with a small fake archive.

Roughly one release (0.5.0), no new permissions, a migration, one new beat entry in `conf/local.py` and `deploy/conf/local.py.append`.

## 7. Decisions and result (2026-10-08)

The owner chose route B the same day, for Pirate, Triglavian and EDENCOM hulls, with this figure: **the average per-run price of the cheapest five runs on offer**, cheapest contracts first. Example: single-run copies at 1, 2, 3, 3, 3 M → (1+2+3+3+3)/5 = 2.4 M per run; a ten-run copy at 1 M per run covers the five runs alone. Regions: The Forge. The copy's ME/TE only shows in the tooltip for now. The member's own right-click price stays on top.

Added safeguard: offers dearer than three times the cheapest per-run price are ignored. Reason from the first snapshot: the Vigilant had three copies at 32 to 37 M and one at 9 B, which would have made the figure 2.3 B.

Built as Shipyard 0.5.0 (runbook 13 C). First snapshot (2026-10-08 08:31 EVE): 49,897 public contracts in the game, 33,811 priced item exchanges in The Forge, 1,101 of them single-blueprint contracts for our 37 hulls; 35 hulls priced, Mekubal and Tholos had no contract at all. Examples per run: Vindicator 16.2 M (47 contracts), Rattlesnake 12.0 M, Machariel 34.0 M, Nightmare 121.6 M, Barghest 223.4 M, Leshak 7.4 M, Thunderchild 660 M, Damavik 1.17 M.
