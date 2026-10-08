# Research: the Reprocessing tab (compressed ore and ice worth buying)

*2026-10-08, desktop session. Owner's request: a second tab in the Shipyard that shows which compressed ores and ice are worth buying at Jita to reprocess, because ore prices are currently favourable. Inspiration: his reprocessing sheet (repro.xlsx) and https://ore.cerlestes.de.*

## 1. The owner's setup

- T2-rigged **Tatara in Sobaseki** (high-sec), **2 % service tax**.
- All reprocessing skills at V, **RX-804** implant (+4 %; the owner wrote "RX04", the 4 % implant is the only RX-x04).
- Only **compressed** ore and ice count; uncompressed and "Batch Compressed" legacy types are left out.

## 2. Yield formula (Upwell structures, EVE University, checked 2026-10-08)

yield = (50 + rig) % × (1 + security) × (1 + structure) × (1 + 0.03 × Reprocessing) × (1 + 0.02 × Reprocessing Efficiency) × (1 + 0.02 × ore skill) × (1 + implant)

| Term | Value here |
|---|---|
| rig | 3 (T2; T1 = 1, none = 0), per kind of ore (asteroid, ice, moon, abyssal each have their own rig) |
| security | 0.00 high-sec (0.06 low, 0.12 null and wormholes; only with a rig) |
| structure | 0.055 Tatara (0.02 Athanor, 0 other Upwell) |
| skills | V, V, V → × 1.15 × 1.10 × 1.10 |
| implant | 0.04 |

Result: (53 %) × 1.055 × 1.15 × 1.10 × 1.10 × 1.04 = **80.9 %** for asteroid ore, ice and moon ore alike (every kind has its own ore skill at V and its own T2 rig). Tax is 2 % of the output value, taken after the yield.

Everything in that table is a setting (`SHIPYARD_REPRO_*` in app_settings.py, override in local.py), so a different structure, implant or tax is a one-line change.

## 3. Data

- **Catalog:** EVE Ref reference data, category 25 (Asteroid): every published type whose name starts with "Compressed ". Per type: group, portion size, volume, `type_materials` (what it reprocesses into, per portion), the required ore skill. Imported by the task `refresh_ore_catalog` (weekly, Sunday 04:20) into the `Ore` table; the output minerals go into `MaterialType`.
- **Portion sizes:** since the 2021 industry changes compression is 1:1 (one Veldspar becomes one Compressed Veldspar at 1/100 of the volume), so compressed asteroid ore still reprocesses in batches of 100 with the same mineral content per unit; compressed ice and moon ore have portion size 1. The dashboard shows figures per unit without batch rounding (in game a job rounds down per batch, which matters only for tiny jobs).
- **Prices:** the existing Jita snapshot (Fuzzwork aggregates, hourly) now also covers every compressed ore and every output mineral. Ore: lowest sell (what you pay from sell orders) and highest buy. Minerals: lowest sell.
- **Families and variants** are derived from the data, not from name lists: ores in one group that give the same materials in the same proportions form a family; the one with the smallest quantities is the base, the others are +5/+10/+15 % (asteroid ore) or +15/+100 % (moon ore). Ice variants are not proportional (Thick Blue Ice gives more heavy water but the same isotopes), so each ice is its own family. This keeps new ores working without code changes.

## 4. Figures per ore

- **Value** per unit = Σ (material quantity ÷ portion size × yield × Jita lowest sell), × (1 − tax).
- **Now** = Jita sell price of the ore ÷ value. Below 100 % the ore is cheaper than its minerals; green at or below 90 %, amber up to 100 %, red above. The buy-order ratio is in the tooltip.
- **Price points** 90, 92, 95, 98, 100 %: the most you can pay per unit to keep the ore at that share of its output value (the owner's wish: "list it as 90 % price").
- **Gives per unit:** the minerals with quantities, hover for unit price and value.

## 5. Filters

Like the ship dashboard: kind buttons (asteroid ore, ice, moon ore, abyssal ore), variant buttons (base, +5, +10, +15, +100 %), a collapsible panel with one button per ore family (Gneiss, Veldspar, Zeolites, …) grouped by kind, and a free-text search that also matches the mineral names. All remembered per browser; nothing ticked shows everything.

## 6. Part B: the Scrapmetal tab (modules bought to reprocess), 2026-10-08

Owner's story: he buys meta modules to reprocess them. Module reprocessing is not affected by the structure, rigs or implants, only by the Scrapmetal Processing skill, so he does it at 0 % tax in the Isikano Raitaru. Question: which modules are favourable to buy, given the Jita sell value of their minerals. Inspiration: his sheet "Faction ships dashboard v2.xlsx", tab "Repro backend" (one column per module group, `ROUNDDOWN(0.55 × quantity)` per mineral, Jita mineral prices, 90/92/95 % price points on the main dashboard).

- **Yield:** 50 % + 2 % per level (55 % at V). Per unit, each mineral is rounded down, as the game and the sheet do; the sheet's figures for the 100MN Monopropellant Enduring Afterburner (9,842 tritanium, 4,416 pyerite, 551 mexallon, 24 isogen, 12 nocxium, 1 zydrine, 0 megacyte) are reproduced exactly.
- **Catalog:** the owner's list of 66 modules in 20 groups (`constants.SCRAP_GROUPS`, names polished: "Heavy energy nosferatus", "Large guns (1400mm, 425mm, Tachyon)" …); names resolved to type ids through ESI, materials and volumes from EVE Ref. Managers can add modules in the admin; the weekly task fills the rest. The sheet also had "cap booster" and "fr-x heavy" columns, which were not in the owner's list for the app.
- **Figures:** Value (minerals at Jita lowest sell, no tax), Sell and Buy of the module, Vol/day and Depth from ESI history, Sell % (what you pay from sell orders; leads the table), Buy %, price points 90/92/95/98/100 %, Gives per unit.
- **Member's skill:** Scrapmetal Processing is now one of the skills read with the character (`UserSettings.scrapmetal_processing`); the tab says whose level is used.
