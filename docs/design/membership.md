# Membership design — The Orlov Family

*Decided 2026-10-01. This is the source of truth for the Alliance Auth configuration (Day 2) and the Discord role layout. No secrets in this file.*

## 1. Entities

| Entity | Type | Ticker | ID | Status |
|---|---|---|---|---|
| The Orlov Family | alliance | `ORLOV` | *(zkillboard URL `/alliance/<id>/`)* | created in-game (before 2026-10-02) |
| Orlov Arms International | corporation | `OARMI` | *(zkillboard URL `/corporation/<id>/`)* | executor corp |
| Gewoon voor structures | corporation | `GWON` | 98635713 | holding corp for the structures, not in the alliance; listed on the state |
| Go Browns | corporation | `GB44` | 98845722 | in the alliance since 2026-10-06, visible in ESI 2026-10-08 (11 members, CEO Masterxxx); members are `Family Member` through the alliance rule. Group and Discord role `corp_GB44` |
| Cartographers | corporation | `1E3` | 98846240 | joining corp (founded 2026-10-09, 2 members, CEO Eemar), not in the alliance yet; **not listed on the state** (owner's rule). Registered in auth 2026-10-10, auto-group `corp_1E3` and Discord role `corp_1E3` (1558471529639976965) created in advance |
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
| `OARMI Director` | manual, hidden, internal | `OARMI Director` | OARMI's corp directors (2026-10-18: the owner, Hamu): gates `#oarmi-directors`, because Discord cannot express "Corp Director AND corp_OARMI" with two roles |
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
- 2026-10-06 — **Go Browns [GB44]** accepted into the alliance; because of the 24 h join delay the corp was added to the `Family Member` state's corporation list as a one-off (like GWON). **To do once ESI shows GB44 inside ORLOV: remove GB44 from the state's corporations again**, so membership follows the alliance. Users Masterxxx and MrFreshy_Valterus also added to the `Corp Director` group (owner's instruction).
- 2026-10-08 — ESI shows Go Browns [GB44] inside ORLOV (scheduled check 12:47 UTC); the one-off removed: GB44 taken off the `Family Member` state's corporation list (backup `aa-db-2026-10-08-1347.sql.gz` first). Masterxxx and MrFreshy_Valterus keep `Family Member` through the alliance rule. The state's corporations are OARMI and GWON again.
- 2026-10-10 — **Cartographers [1E3]** (corp 98846240, founded 2026-10-09, 2 members, CEO Eemar, no alliance) prepared ahead of its members authing per the 2026-10-05 rule: corporation registered in auth (pk 14), auto-group `corp_1E3` created in advance (group pk 14, managed link pk 10, 0 members), **not** listed on the `Family Member` state. Discord role `corp_1E3` (1558471529639976965) created in advance with the Discord client's `match_or_create_role_from_name()` once the owner had added a permission rule for `ssh orlov` commands on the PC (the desktop session's classifier had blocked the Discord write at first). When Eemar has authed: add them to `Corp Director` and have them add the Corp Stats / Member Audit token (`docs/guides/corp-ceo-onboarding.md`).
- 2026-10-10 — Eemar (CEO of Cartographers [1E3], authed as user `Eemar`, state Family Friend, Discord linked) added to the `Corp Director` group on the owner's instruction; the Discord role followed within seconds. Still open for Eemar: the Corp Stats / Member Audit token (`docs/guides/corp-ceo-onboarding.md`).
- 2026-10-20 — **Kitten_Kerns** (main Kitten Kerns, OARMI; Discord dominikstarz) locked out of Family Member on the owner's instruction while still in the corp: new state **`Family Friend (locked)`** (priority 150, above Family Member's 100, not public, Family Friend's two permissions, membership by character only: Kitten Kerns 95662236). Because the state is tied to his character and outranks the corp rule, he cannot regain Family Member while his character is listed there; moving him back = remove the character from that state in the admin (Authentication → States). He keeps Family Friend-level access: the Discord role `Family Friend (locked)` (1561955193091006534) got the same overwrites as `Family Friend` on all 15 channels and categories that mention it. Effects: groups now none (corp_OARMI dropped by autogroups), Discord roles now `Family Friend (locked)` only, nickname unchanged `[OARMI] Kitten Kerns`. Done by the desktop session from the shell (the Discord sync needed a retry after the rate limiter).
- 2026-10-18 — Two Discord channels for OARMI, made by the desktop session through the bot: `#oarmi-corp` (1561412024636805130) under Member channels, visible to `corp_OARMI` only (every role the category lets in is denied on the channel, @everyone denied); `#oarmi-directors` (1561412026167722094) under Alliance Leadership, visible to the new role `OARMI Director` only (`Corp Director` and @everyone denied on the channel). Both allow the full chat set: send, history, links, attachments, external emojis and stickers (GIFs), reactions, threads, polls, voice messages, slash commands. The auth group `OARMI Director` (hidden, internal) holds the owner and Hamu; add a director there and the Discord role follows.
- 2026-10-18 — Hamu (user `Hamu`, main Hamu, OARMI) added to the `Corp Director` group on the owner's instruction (desktop session, from the shell); the Discord role pushed in the same step.
- 2026-10-14 — Corp Stats permissions: `Corp Director` gets *Can add corp stats* and *Can view corp stats*, `Alliance Director` those plus *Can view alliance corp stats* (nobody but the superuser held them before, so a CEO following the onboarding guide would have been refused). Runbook 15 written for CEOs and directors. Occasion: 5 of 43 alliance characters are not in auth (OARMI: Goedweer2–5, Miguel Stevens; 1E3: one unnamed, Eemar's token lacks the membership scope).
