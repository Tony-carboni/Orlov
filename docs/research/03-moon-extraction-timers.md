# Moon extraction timers for the Athanors — what exists, how the data flows

*Research 2026-10-02. Question: show when each Athanor's moon chunk arrives ("moon pop"), ideally in Discord, acceptably in auth.*

*Update 2026-10-04: the Athanor was anchored under a one-man **holding corp** (keeps OARMI/ORLOV war-immune), so tokens come from the holding-corp CEO, not OARMI. Public Athanors can't be read via ESI; they go on the board by hand via aa-structuretimers. Build steps: `docs/runbooks/07-day-five-moon-timers.md`.*

## 1. Where the information comes from (ESI)

Two independent sources, both read with a corp-level token from a character **in the owning corp (OARMI)**:

| Source | Endpoint | Scope | In-game role needed | What you get |
|---|---|---|---|---|
| **Extraction timers** | `GET /corporation/{corp_id}/mining/extractions/` (cached 30 min) | `esi-industry.read_corporation_mining.v1` | **Station Manager** | per refinery: `structure_id`, `moon_id`, `extraction_start_time`, **`chunk_arrival_time`** (the pop; when the chunk can be fractured), `natural_decay_time` (auto-fracture if nobody fires the laser, ~3 h later) |
| **Notifications** | `GET /characters/{char_id}/notifications/` (cached 10 min) | `esi-characters.read_notifications.v1` | the character must receive them (Station Manager / Director) | `MoonminingExtractionStarted` (schedule set, includes ready time and ore volumes), `MoonminingExtractionFinished` (chunk arrived), `MoonminingAutomaticFracture`, `MoonminingLaserFired`, `MoonminingExtractionCancelled` |

Both are in the scope list the EVE developer app already has (all `esi-*` ticked on Day 0). The extraction list is the authoritative timer; notifications are what make Discord alerts possible and carry the ore composition.

## 2. What already exists (Alliance Auth ecosystem, all free, all maintained)

| App | Latest | Does | Discord? | Needs |
|---|---|---|---|---|
| **aa-structures** | 4.0.4 | Lists all corp structures with fuel/state; **forwards EVE notifications to Discord webhooks by category — Moon Mining is one** (extraction started / finished / auto-fracture / laser fired); can auto-add timers to a timer board | **Yes** — webhook alerts in a channel of your choice, e.g. `#moon-timers`, with the chunk arrival time in the "started" alert and a ping when it lands | Director token from OARMI; `django-eveuniverse` (already installed) |
| **aa-moonmining** | 3.1.0 | The moon board: owned moons, **upcoming and past extractions with timers**, ore composition, ISK value per extraction, mining ledger (who mined what), moon survey database | No own Discord output (only admin notices) | Station Manager token; `eveuniverse`; two one-off data loads (ores, prices) |
| **aa-opcalendar** | 4.0.1 | Ops calendar; **integrates aa-moonmining so extractions appear as calendar events**; iCal feed; optional Discord bot that keeps a pinned "upcoming events" embed in a channel + reminder pings (1 h / 1 day before) | Yes (webhook + optional bot) | aa-moonmining for the moon events |
| aa-structuretimers | 3.2.0 | Timer board II (reinforcement timers), Discord notifications | Yes | mostly for structure fights; moon pops only if you enter them by hand |
| AA built-in `timerboard` | — | manual timer board | via discordbot `/timers` cog | manual entry — not what you want |

Nothing outside the AA ecosystem does this better for a small alliance; third-party hosted tools (e.g. Eve-Moons sites) require the same tokens and give you less.

## 3. Recommendation

**Install `aa-structures` + `aa-moonmining`** — together they cover exactly the ask:

- **Discord (primary):** `aa-structures` posts to a webhook in a `#moon-timers` channel: when an extraction is scheduled ("chunk arrives <date time>, est. <m³> of <ores>"), when it arrives, and when it's fractured. Members with the role see the channel; no bot interaction needed.
- **Auth (board):** `aa-moonmining` → *Extractions* page: every Athanor, next chunk time, countdown, estimated ISK, plus the ledger afterwards. Leadership-only or members, by permission.
- Bonus from `aa-structures`: fuel-low alerts and structure attack/reinforce alerts for the same Athanors — the thing alliances usually install it for anyway.

Optional later: `aa-opcalendar` if you want moon pops in a calendar with the rest of the alliance's ops and a pinned Discord summary.

## 4. What it takes (Day 5 build, ~1.5 h + data loads)

1. Same custom-image pattern as Member Audit: add `aa-structures==4.0.4` and `aa-moonmining==3.1.0` to `conf/requirements.txt`, build, `up -d`, restart nginx, migrate, collectstatic.
2. `local.py`: `INSTALLED_APPS += ["structures", "moonmining"]` plus their beat schedules (structures: notification pull every ~1 min, structure refresh; moonmining: regular updates every 10 min, reports hourly, values daily).
3. One-off loads: `moonmining_load_eve` (ores) and `moonmining_calculate_all` (prices); structures loads types on demand.
4. Discord: create a webhook on a new `#moon-timers` channel (channel → Edit → Integrations → Webhooks → New → copy URL) and paste it into `aa-structures`' admin → Webhooks, set as default, tick the *Moon Mining* notification types (and fuel/attack if wanted).
5. Tokens: in auth, *Structures → Add Owner* with your main (needs **Director** in OARMI — you have it) and *Moon Mining → Add Owner* with the same character (needs **Station Manager**; Director covers it). Any future corp with its own Athanors does the same with its own CEO.
6. Permissions: `structures.basic_access` + `moonmining.basic_access` to `Family Member` if members may see the board; `moonmining.extractions_access`, `moonmining.add_refinery_owner`, `structures.add_structure_owner` to `Corp Director`/`Alliance Director`.

Trade-offs to be aware of:
- Notification matching is best-effort: ESI only returns recent notifications, so an extraction scheduled weeks ago may show a timer without ore details (README FAQ). The timer itself always comes from the extractions endpoint.
- Both apps poll ESI continuously; on the 4 GB server that's fine for a handful of structures.
- The webhook route means alerts work even without the discordbot.

## Sources
- aa-structures: https://github.com/AllianceAuth-Apps/aa-structures (features list: notification forwarding incl. Moon Mining; timer board integration)
- aa-moonmining: https://github.com/AllianceAuth-Apps/aa-moonmining (README: features, installation steps 1–8, scopes, permissions, FAQ on notification matching)
- aa-opcalendar: https://gitlab.com/paulipa/allianceauth-opcalendar (README: moonmining integration, Discord bot/webhooks, iCal)
- aa-structuretimers: https://github.com/AllianceAuth-Apps/aa-structuretimers
- ESI mining extractions endpoint (goesi reference): https://github.com/antihax/goesi/blob/master/esi/docs/IndustryApi.md — "Requires one of the following EVE corporation role(s): Station_Manager", cached 1800 s; fields: https://github.com/a-tal/goesi/blob/162ed0c4b1c2/esi/docs/GetCorporationCorporationIdMiningExtractions200Ok.md
- Versions from PyPI JSON on 2026-10-02.
