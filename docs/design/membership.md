# Membership design — The Orlov Family

*Decided 2026-10-01. This is the source of truth for the Alliance Auth configuration (Day 2) and the Discord role layout. No secrets in this file.*

## 1. Entities

| Entity | Type | Ticker | ID | Status |
|---|---|---|---|---|
| The Orlov Family | alliance | `ORLOV` | *(zkillboard URL `/alliance/<id>/`)* | created in-game (before 2026-10-02) |
| Orlov Arms International | corporation | `OARMI` | *(zkillboard URL `/corporation/<id>/`)* | executor corp |
| — | allied (Family Friend) | — | — | not needed: Family Friend is a public state |

The `Family Member` state is keyed on **alliance ORLOV** (member alliances) with corp OARMI also listed (harmless, kept as belt-and-braces). New corps joining the alliance are covered automatically.

## 2. States (mutually exclusive; highest priority wins; AA syncs the state name as a Discord role)

| State | Priority | Qualifies if main character is in… | Discord role | Discord access |
|---|---|---|---|---|
| `Family Member` | 100 | alliance ORLOV (+ corp OARMI) | `Family Member` | yes |
| `Family Friend` | 50 | **any other character** (state is *Public*) — anyone who authenticates but isn't an alliance main | `Family Friend` | yes — role tag + `[TICKER] Name` nickname only; no extra channels |
| `Guest` | — | only deactivated/unverified accounts now (built in) | none | no — removed from server |

## 3. Groups → Discord roles

| AA group | Type | Discord role | Who grants |
|---|---|---|---|
| `corp_<TICKER>` (e.g. `corp_OARMI`) | auto-group: prefix `corp_`, name source = ticker | `corp_<TICKER>` | AA, automatically |
| `Alliance Director` | manual, hidden | `Alliance Director` | alliance executor, in AA admin |
| `Corp Director` | manual, hidden (later: automatic from in-game Director role via plugin) | `Corp Director` | alliance executor / corp CEOs |
| `FC` | request + approval | `FC` | FC lead |

Discord role hierarchy (top → bottom): bot role · Alliance Director · Corp Director · FC · Family Member · Family Friend · corp_* · @everyone.

## 4. Policies

| # | Policy | Decision | Consequence for configuration |
|---|---|---|---|
| 1 | Character registration | **Main required; alts encouraged, not enforced.** | Member Audit compliance group is **not** used to strip roles. Corp Stats still shows unregistered characters so leadership can nudge people. |
| 2 | Inactivity | **60 days** without logging in = inactive. | Member Audit / Corp Stats report flags >60 d. Action on inactive members is a leadership decision, not automated (can be automated later via a custom plugin that drops a group → role). |
| 3 | Fleet participation (PAP) | **Not tracked.** | `allianceauth-afat` is **not** installed in Phase 4. Can be added later without migration pain. |
| 4 | Corp token responsibility | **The CEO** of each member corp adds the Corp Stats / Member Audit director token. | Runbook for CEOs in `docs/runbooks/` (Phase 4). |
| 5 | Discord nickname | **`[OARMI] Character Name`** — corp ticker in brackets, then the main character's name. | AA core: `DISCORD_SYNC_NAMES = True` + admin *Services → Name format config* for Discord: `[{corp_ticker}] {character_name}`. The server **owner** is the one account a bot can't rename (403) — the owner sets their own nickname by hand; AA's failed nickname task for the owner only logs an error (verified: it does not unlink or kick). Discord nicknames are capped at 32 characters. |

## 5. Change log

- 2026-10-01 — initial version (roles created in Discord; policies decided).
- 2026-10-02 — alliance exists in-game; `Family Member` state keyed on alliance ORLOV.
- 2026-10-02 — `Family Friend` made a **public state**: any authenticated non-member gets it (nickname + role tag, public channels only). Discord: `#public-chat` open to unauthenticated visitors too; `#how-to-auth`/`#rules` read-only.
- 2026-10-02 — `DISCORD_SYNC_NAMES` temporarily `False` so the owner could activate (403 on owner nickname); re-enabled on Day 3 with the `[{corp_ticker}] {character_name}` formatter. discordbot deferred until there are members.
