# Research: weekly or monthly reports on corporation projects

*2026-10-12, desktop session. Owner's question: can we report on the corp's projects, such as ISK paid out and ore volume delivered, per week or month?*

**Short answer: yes.** Since late 2025 ESI has read routes for corporation projects (checked against the live spec on 2026-10-12, compatibility date 2026-08-18). Nothing in our stack reads them yet, and no token on the server carries the scope, so it is a small build: a token, an hourly snapshot task and a report.

## 1. What ESI gives

Scope `esi-corporations.read_projects.v1`, four routes, cursor-paged (`after`/`before`, `limit` 10 by default):

| Route | Gives |
|---|---|
| `GET /corporations/{id}/projects?state=All` | every project: id, name, state (Active, Closed, Completed, Expired, Deleted), progress current/desired, reward initial/remaining (ISK), last modified |
| `GET /corporations/{id}/projects/{project_id}` | the details: creator, career, created/expires/finished, description, contribution rules (reward per contribution, participation and submission limits, multiplier) and the configuration: what counts (deliver item with the item types and docking locations, mine material with locations and ore types, manufacture item, destroy ship, and so on) |
| `GET /corporations/{id}/projects/{project_id}/contributors` | every contributor with the amount contributed |
| `GET /corporations/{id}/projects/{project_id}/contribution/{character_id}` | one character's own contribution |

The routes only exist under the new ESI versioning: calls must send the `X-Compatibility-Date` header (any date from 2025-09-30 on). The legacy `/latest/` spec does not list them, which is why older libraries do not know them.

Not stated in the spec: which corporation role the character needs. The own-contribution route suggests any member can read the list; the contributors list may need a director or the project's manager. Catherine Frey (CEO) covers every case.

## 2. What a report can contain

Per project and per period (week or month, by `finished` or by the snapshot dates):

- **ISK paid out:** reward initial minus remaining, or Σ contributed × reward per contribution, capped by the pool.
- **Volume delivered:** progress current is in the project's own units (items delivered, ore units mined); multiply by the type's volume for m³ and by Jita prices (the Shipyard's price snapshot) for the market value of what came in.
- **Per member:** contributions and the share of the payout, which doubles as a leaderboard.
- **Pipeline:** active projects with progress and remaining pool, expiring soon.

## 3. Caveats

- ESI returns totals, not a history. A project that ran for two months shows one progress figure. To slice by week we store an hourly snapshot and difference the snapshots; the report is only as old as the first snapshot, so the sooner the task runs, the longer the history.
- How long finished projects stay in `state=All` is not documented. Snapshots cover that as well.
- Deleted projects may lose their contributors.

## 4. Build (one release, Shipyard or a small `projects` app)

1. Scope: add `esi-corporations.read_projects.v1` to the character grant (the Shipyard's `FULL_SCOPES`, or a separate SSO button for the CEO); Catherine logs in once.
2. Task every hour: list projects (`state=All`), fetch details for new or changed ones (`last_modified`), fetch contributors; store a snapshot row per project and per contributor with the time.
3. Report: a page in the Shipyard (period picker, totals, per project, per member) and, if wanted, the bot posts the weekly summary to a Discord channel on Monday morning.
4. Later: the Shipyard's own price and volume data to value ore deliveries.

Owner decides: Shipyard tab or separate app, Discord post yes or no and to which channel, week or month as the default period.
