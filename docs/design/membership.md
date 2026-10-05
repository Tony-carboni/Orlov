# Membership design — The Orlov Family

*Decided 2026-10-01. This is the source of truth for the Alliance Auth configuration (Day 2) and the Discord role layout. No secrets in this file.*

## 1. Entities

| Entity | Type | Ticker | ID | Status |
|---|---|---|---|---|
| The Orlov Family | alliance | `ORLOV` | *(zkillboard URL `/alliance/<id>/`)* | created in-game (before 2026-10-02) |
| Orlov Arms International | corporation | `OARMI` | *(zkillboard URL `/corporation/<id>/`)* | executor corp |
| Gewoon voor structures | corporation | `GWON` | 98635713 | holding corp for the structures, not in the alliance; listed on the state |
| Go Browns | corporation | `GB44` | 98845722 | joining corp, **not yet in the alliance** on 2026-10-05 (11 members, CEO Masterxxx). Its members are `Family Friend` until the corp is in the alliance in game; then `Family Member` follows automatically. Group and Discord role `corp_GB44` exist already |
| — | allied (Family Friend) | — | — | not needed: Family Friend is a public state |

The `Family Member` state is keyed on **alliance ORLOV** (member alliances) plus two corporations: OARMI (harmless, kept as belt-and-braces) and GWON (the owner's structure holding corp). New corps joining the alliance are covered automatically.

**Rule (owner, 2026-10-05): a joining corp is not listed on the state.** Nobody gets `Family Member` before their corp is actually in The Orlov Family in game; until then its members are `Family Friend`. Prepare a joining corp only by registering it and creating its `corp_<TICKER>` group and Discord role.

## 2. States (mutually exclusive; highest priority wins; AA syncs the state name as a Discord role)

| State | Priority | Qualifies if main character is in… | Discord role | Discord access |
|---|---|---|---|---|
| `Family Member` | 100 | alliance ORLOV, or corp OARMI or GWON | `Family Member` | yes |
| `Family Friend` | 50 | **any other character** (state is *Public*) — anyone who authenticates but isn't an alliance main | `Family Friend` | yes — role tag + `[TICKER] Name` nickname only; no extra channels |
| `Guest` | — | only deactivated/unverified accounts now (built in) | none | no — removed from server |

## 3. Groups → Discord roles

| AA group | Type | Discord role | Who grants |
|---|---|---|---|
| `corp_<TICKER>` (e.g. `corp_OARMI`) | auto-group: prefix `corp_`, name source = ticker | `corp_<TICKER>` | AA, automatically |
| `Alliance Director` | manual, hidden | `Alliance Director` | alliance executor, in AA admin |
| `Corp Director` | manual, hidden (later: automatic from in-game Director role via plugin) | `Corp Director` | alliance executor / corp CEOs |
| `FC` | request + approval | `FC` | FC lead |
| `Early Founders` | manual, badge only: no permissions in auth or Discord | `Early Founders` | the local session, on the owner's request ("refresh the founders") |

**Early Founders rule (owner's decision 2026-10-05):** every account with the `Family Member` state before **2027-01-01** is a founder. Go Browns members count once their corp is in the alliance and they are `Family Member`. It is add-only: a founder keeps the group as long as the account exists, and nobody is added from 2027 on. New members during 2026 do not get it automatically; the owner asks a session to refresh, which adds every current Family Member account to the group. The role must stay an auth group: auth removes Discord roles it does not manage at its next sync.

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
- 2026-10-02 — first real member's nickname stayed `[SWA]` after moving corp: AA only sets nicknames on activation/main change. Added `discord.update_all_nicknames` every 6 h.
- 2026-10-02 — `Family Friend` made a **public state**: any authenticated non-member gets it (nickname + role tag, public channels only). Discord: `#public-chat` open to unauthenticated visitors too; `#how-to-auth`/`#rules` read-only.
- 2026-10-05 — Go Browns [GB44] (corp 98845722, not yet in the alliance) prepared ahead of its members authing: corporation registered in auth, auto-group `corp_GB44` and Discord role `corp_GB44` created in advance. It was briefly listed on the `Family Member` state and taken off again the same day (owner: no Family Member before the corp is in the alliance).
- 2026-10-05 — `Early Founders` badge group and Discord role created (first named `Founder`, renamed the same day); first four founders: tony (Catherine Frey), Flapoor_Hendrik (main Gewoon Rudi), Nashomon Yoma Itinen, Tavaga.
- 2026-10-02 — `DISCORD_SYNC_NAMES` temporarily `False` so the owner could activate (403 on owner nickname); re-enabled on Day 3 with the `[{corp_ticker}] {character_name}` formatter. discordbot deferred until there are members.
