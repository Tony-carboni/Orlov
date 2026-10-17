# Doctrines — The Orlov Family's fleet doctrines behind auth

An Alliance Auth plugin that serves the alliance's fleet doctrines under their own hostname
(`doctrines.orlovfamily.space`), readable only by members with the permission `doctrines.basic_access`
(given to the `Family Member` state, so alliance members only). Runbook 16 covers the rollout.

## What members see

- **Landing page:** the alliance's philosophy (editable text) and the doctrines as clickable tiles in four
  rows: Light & cheap, Bread and butter, Support, APEX. A tile shows the doctrine's name, its gameplay
  (home defense, faction warfare, wormhole, nullsec roam, ...), a summary and the ship pictured.
- **Doctrine page:** description, pros, cons, strategy notes, and the ships: role, **cost** (hull plus
  everything fitted and carried, at Jita IV-4 lowest sell), **net insurance** (Platinum payout minus
  premium, from EVE's insurance table), **loss if lost** (cost minus net insurance), the **SRP level**.
  Clicking a ship opens its fitting: the hull's render, the modules by slot with icons, drones and
  cargo, and a **Copy fit to clipboard** button (the game's fitting window → Import from clipboard);
  "Open as text" is the fallback when a browser blocks the clipboard.

## How it is edited

In auth's admin (members with `doctrines.manage_doctrines`, the superuser always):

- **Doctrines → Landing page text**: the philosophy. Plain text; a blank line is a new paragraph,
  a line starting with `- ` is a bullet.
- **Doctrines → Categories** and **SRP levels**: seeded by `manage.py doctrines_seed`, editable.
- **Doctrines → Doctrines**: one per doctrine, with its ships inline. A ship's fitting is pasted
  exactly as the game exports it (fitting window → Export → To clipboard). On save the text is
  parsed and every item resolved to an EVE type (ESI, cached in `ItemType`); the parse result is
  stored on the ship and a problem shows in the "parse error" field. New types are priced at once.

## Background tasks

| Task | Beat entry | Schedule |
|---|---|---|
| `doctrines.tasks.refresh_prices` | `doctrines_refresh_prices` | hourly at :35, every type in an active fitting, Fuzzwork station aggregates |
| `doctrines.tasks.refresh_insurance` | `doctrines_refresh_insurance` | daily at 05:40, EVE's insurance table at the configured level |

## Settings (`conf/local.py`)

| Setting | Default | Meaning |
|---|---|---|
| `DOCTRINES_HOST` | `""` | the doctrines' hostname; `""` keeps them on auth's host only |
| `DOCTRINES_MARKET_STATION_ID` | `60003760` | Jita IV-4, for the prices |
| `DOCTRINES_MARKET_NAME` | `"Jita IV-4"` | shown on the page |
| `DOCTRINES_PRICE_MAX_AGE_HOURS` | `2` | older prices are flagged on the page |
| `DOCTRINES_INSURANCE_LEVEL` | `"Platinum"` | the insurance level used |
| `DOCTRINES_BRAND` | `"Orlov Doctrines"` | the top bar's name on the standalone pages |

The second hostname works the way the Shipyard's does: `doctrines.middleware.DoctrinesHostMiddleware` in
`MIDDLEWARE`, the session and CSRF cookies on `.orlovfamily.space`, the hostname in `CSRF_TRUSTED_ORIGINS`.

## Install

```
orlov-doctrines @ https://github.com/Tony-carboni/Orlov/archive/<commit>.tar.gz#subdirectory=apps/doctrines
```

Add `"doctrines"` to `INSTALLED_APPS`, the settings block from `deploy/conf/local.py.append`, migrate,
`doctrines_seed`, collectstatic, give the permission to the `Family Member` state.

## Tests

`python manage.py test doctrines` (the parser and the pages; no EVE calls).
