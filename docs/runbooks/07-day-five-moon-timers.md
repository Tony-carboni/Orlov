# Day 5 runbook — moon timers in Discord and on auth

*Prerequisite: Days 0–4 and runbook 06 complete. First Athanor online with an extraction running (done 2026-10-04).*
*Time: ~1.5 h, of which ~45 min is waiting for EVE data loads. Server sections are run by Claude in the **local session** (say "run Day 5 section B"); browser and Discord sections are yours.*
*Convention: one code block = one Enter. Blocks that must be pasted whole are labelled.*

**Goal:** every moon extraction shows up as a timer, both in Discord (`#moon-timers`: "chunk arrives Fri 16 Oct 18:00", a reminder 1 h before, and "field is up") and on auth (a timer board plus the Moon Mining page with ore values and the mining ledger). Public Athanors in Piekura can be added to the same board by hand.

Decisions baked in (research in `docs/research/03-moon-extraction-timers.md`):
- Three apps: **aa-structures** (reads the Athanor and its EVE notifications → Discord), **aa-moonmining** (extraction board, ore value, ledger), **aa-structuretimers** (timer board II; own extractions are added automatically, other people's by hand; sends the 1-hour reminders).
- The Athanor is owned by your **one-man holding corp**, not OARMI (keeps OARMI and the alliance war-immune). So the ESI tokens come from your **holding-corp character**, which must be registered on auth as an alt of your account. It is CEO there, which covers the Director and Station Manager roles the apps need.
- Member-facing channel **`#moon-timers`** under `ALLIANCE` (Family Member can read, nobody but the webhook posts). Fuel-low and attack alerts go to **`#directors`**.
- Members get read access to the timers and the Moon Mining board. Only `Alliance Director` can add owners/tokens or edit timers.

## Known values

| Item | Value |
|---|---|
| Server | `ssh orlov` → `~/aa-docker` (local session runs this) |
| Admin | https://auth.orlovfamily.space/admin/ |
| Packages added | `aa-structures==4.0.4`, `aa-moonmining==3.1.0`, `aa-structuretimers==3.2.0` |
| Token character | Flapoor Hendrik, CEO of "Kazen die stinken zijn lekkerder" [KHAAS] (started the extraction) |
| Channels | `#moon-timers` (new, ALLIANCE category), `#directors` (exists) |

---

## A. Preparation (browser + Discord, 10 min)

**A1. Register the holding-corp character on auth.** Done on the server side 2026-10-04 (Flapoor Hendrik was detached from the test user; see `docs/handoff.md`). What remains is yours: log in to https://auth.orlovfamily.space with your **own `tony` account** (SSO with Catherine Frey or any character already on it) → dashboard → **Add Character** → log in with **Flapoor Hendrik** in the EVE SSO window → accept all scopes. He appears as an alt with corp "Kazen die stinken zijn lekkerder", no alliance; your state stays `Family Member` (states follow the main). ⚠️ Don't log in with Flapoor Hendrik while logged out of auth — that creates a separate user. Then **Member Audit → Add character** → Flapoor Hendrik again (his old token only had public scopes).

**A2. Create `#moon-timers`** in Discord: right-click the `ALLIANCE` category → **Create Channel** → text, name `moon-timers`. Channel → **Edit Channel → Permissions**: `Family Member` View ✅ Send ❌; `Family Friend` ❌; `@everyone` ❌ (friends don't mine our moons). Leave the category default otherwise.

**A3. Create two webhooks** and keep the URLs somewhere private (Bitwarden note "Discord webhooks"; they are secrets — anyone with the URL can post as the bot):
- `#moon-timers` → **Edit Channel → Integrations → Webhooks → New Webhook** → name `Moon Timers` → **Copy Webhook URL**.
- `#directors` → same → name `Structure Alerts` → copy URL.

**A4. Backup** — in the local session say "run the backup script" (it runs `~/bin/aa-backup.sh` and shows the result).

✅ Done when the alt shows on your dashboard, `#moon-timers` exists and you have two webhook URLs saved.

## B. Install the three apps (server — local session)

*Done 2026-10-04 by the local session; details in `docs/handoff.md`.*

```bash
cd ~/aa-docker
```

**B1. Add the packages** to the custom-image requirements:

```bash
printf 'aa-structures==4.0.4\naa-moonmining==3.1.0\naa-structuretimers==3.2.0\n' >> conf/requirements.txt
```

```bash
cat conf/requirements.txt
```

✅ Four lines: memberaudit, structures, moonmining, structuretimers.

**B2. Settings** — **paste as one block** (ends at `PYEOF`):

```bash
cat >> conf/local.py <<'PYEOF'

# --- Day 5: moon timers (aa-structures, aa-moonmining, aa-structuretimers) --
INSTALLED_APPS += [
    "structures",        # structures + EVE notifications -> Discord webhooks
    "moonmining",        # extraction board, ore values, mining ledger
    "structuretimers",   # timer board II (own extractions auto-added, others by hand)
]

# structures: owned by the holding corp only; no POS / POCO / skyhooks to track
STRUCTURES_FEATURE_STARBASES = False
STRUCTURES_FEATURE_CUSTOMS_OFFICES = False
STRUCTURES_FEATURE_SKYHOOKS = False
STRUCTURES_ADD_TIMERS = True                  # push extraction timers into structuretimers
STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED = True
STRUCTURES_NOTIFICATION_SHOW_MOON_ORE = True  # ore list in the Discord "extraction started" post

CELERYBEAT_SCHEDULE["structures_update_all_structures"] = {
    "task": "structures.tasks.update_all_structures",
    "schedule": 1800,
}
CELERYBEAT_SCHEDULE["structures_fetch_all_notifications"] = {
    "task": "structures.tasks.fetch_all_notifications",
    "schedule": 300,
}

CELERYBEAT_SCHEDULE["moonmining_run_regular_updates"] = {
    "task": "moonmining.tasks.run_regular_updates",
    "schedule": crontab(minute="*/10"),
}
CELERYBEAT_SCHEDULE["moonmining_run_report_updates"] = {
    "task": "moonmining.tasks.run_report_updates",
    "schedule": crontab(minute="30", hour="*/1"),
}
CELERYBEAT_SCHEDULE["moonmining_run_value_updates"] = {
    "task": "moonmining.tasks.run_calculated_properties_update",
    "schedule": crontab(minute="30", hour="3"),
}

CELERYBEAT_SCHEDULE["structuretimers_housekeeping"] = {
    "task": "structuretimers.tasks.housekeeping",
    "schedule": 10800,
}
CELERYBEAT_SCHEDULE["structuretimers_dispatch_scheduled_notifications"] = {
    "task": "structuretimers.tasks.dispatch_scheduled_notifications",
    "schedule": 60,
}
PYEOF
```

```bash
tail -5 conf/local.py
```

**B3. Build and roll out** (~5 min build):

```bash
docker compose --env-file=.env build
```

✅ ends with `exporting to image`, no red `ERROR`.

```bash
docker compose --env-file=.env up -d
```

```bash
docker compose restart nginx
```

**B4. Migrate, static files, data loads.** (Local session: `auth` is a shell alias that only exists in an interactive container shell; run `python /home/allianceauth/myauth/manage.py <command>` through `docker compose exec -T allianceauth_gunicorn` instead, with `--noinput` where the command accepts it.)

```bash
docker compose exec allianceauth_gunicorn bash
```

inside the container:

```bash
auth check
```

```bash
auth migrate
```

```bash
auth collectstatic --noinput
```

```bash
auth eveuniverse_load_data map
```

(Loads all regions, constellations and solar systems so the timer board can pick "Piekura". Answer `y`. Queued in the background; took under 10 min on 2026-10-04.)

```bash
auth structures_load_eve
```

```bash
auth structuretimers_load_eve
```

```bash
auth moonmining_load_eve
```

(Ore types, answer `y`.)

```bash
exit
```

```bash
docker compose ps | grep -E "gunicorn|beat|worker"
```

✅ All `Up`; left menu on auth shows **Structures**, **Moon Mining**, **Structure Timers**. Watch the dashboard's *Task Queue* panel; continue with C while it drains, but don't do E until *queued* is back to 0.

## C. Webhooks and notification routing (browser, 10 min)

**C1. aa-structures webhooks** — https://auth.orlovfamily.space/admin/structures/webhook/add/, twice:

| Field | Webhook 1 | Webhook 2 |
|---|---|---|
| Name | `Moon Timers` | `Structure Alerts` |
| URL | the `#moon-timers` URL from A3 | the `#directors` URL from A3 |
| Notification types | the five that start with `Moonmining` (ExtractionStarted, ExtractionFinished, AutomaticFracture, LaserFired, ExtractionCancelled) | everything that starts with `Structure` (fuel alert, under attack, lost shields/armor, destroyed, low power, services offline, anchoring/unanchoring, reinforcement changed, refueled) |
| Is default | ✅ | ✅ |
| Is active | ✅ | ✅ |

**Save** each. Then on the webhook list, tick both → action **Send test notification** → Go. ✅ A test message appears in each channel.

**C2. aa-structuretimers webhook + rules** — https://auth.orlovfamily.space/admin/structuretimers/webhook/add/: name `Moon Timers`, URL = the `#moon-timers` URL, Is enabled ✅, Save. Then https://auth.orlovfamily.space/admin/structuretimers/notificationrule/add/ — if that link 404s use **Admin → Structure Timers → Notification rules → Add**. Two rules:

| Field | Rule 1 (reminder) | Rule 2 (go time) |
|---|---|---|
| Trigger | Scheduled time reached | Scheduled time reached |
| Scheduled time | 60 minutes before | 0 minutes (at the time) |
| Webhook | `Moon Timers` | `Moon Timers` |
| Ping type | none | `@here` |
| Require timer types | `Moon Mining` | `Moon Mining` |
| Is enabled | ✅ | ✅ |

Leave the other filter clauses empty (apply to all moon timers, ours and public ones). Do **not** add a "new timer created" rule — the aa-structures "extraction started" post already covers our moons and would double up.

## D. Permissions (browser, 5 min)

*Done 2026-10-04 by the local session (via Django, see `docs/handoff.md`).*

`Family Member` is a **state**, not a group: https://auth.orlovfamily.space/admin/authentication/state/. The two director groups are at https://auth.orlovfamily.space/admin/groupmanagement/group/. Open each → **Permissions** box (search by the text after the pipe):

| State / group | Add permissions |
|---|---|
| `Family Member` (state) | `moonmining \| general \| Can access the moonmining app`, `moonmining \| general \| Can access extractions and view owned moons`, `structuretimers \| general \| Can access this app and see timers` |
| `Alliance Director` (group) | all of the above plus `moonmining \| general \| Can add refinery owner`, `moonmining \| general \| Can view moon ledgers`, `moonmining \| general \| Can access reports`, `structures \| general \| Can access this app and view public pages`, `structures \| general \| Can add new structure owner`, `structures \| general \| Can view all structures`, `structures \| general \| Can view structure fit`, `structuretimers \| general \| Can create new timers and edit own timers`, `structuretimers \| general \| Can edit and delete any timer` |
| `Corp Director` (group) | `structures \| general \| Can access this app and view public pages`, `structures \| general \| Can view corporation structures`, `structuretimers \| general \| Can create new timers and edit own timers` |

The Structures "access this app" permission is required for the other Structures permissions to do anything. **Save** each. Log out and in once so your own permissions refresh.

## E. Register the Athanor (browser, 5 min — after the task queue is empty)

**E1. Structures → Add Owner** (left menu). The SSO window opens: log in with the **holding-corp character**, accept the scopes. ✅ Within a minute the Structures page lists the Athanor with fuel days; `#directors` may get a "structures owner added" note.

**E2. Moon Mining → Add Owner** → same character, accept. ✅ Moon Mining → *Extractions* shows your moon with the chunk arrival time; *Owned Moons* lists it. Values fill in at the next hourly report run.

**E3. Structure Timers** (left menu) → the extraction appears as a `Moon Mining` timer with the arrival time (added by aa-structures from the `MoonminingExtractionStarted` notification; up to 5 min after E1). If it doesn't within 15 min, see Troubleshooting.

**E4. Discord** → `#moon-timers` has the "Extraction started" post with the ore list and arrival time. The reminder and `@here` posts come from the rules in C2 when the time arrives.

## F. Public Athanors in Piekura (optional, by hand)

ESI only exposes extractions to the owning corp, so other people's cycles can't be read automatically. What you can do:

1. Find the pop time: look at the structure's **name or description** in the Structure Browser (public-access Athanors often publish their frack schedule there), ask the owner in local/mail, or note when the belt appeared (d-scan asteroids at that moon; a field lasts ~48 h and most owners run a fixed 7- or 14-day rhythm, so the next one is predictable).
2. **Structure Timers → Add Timer**: Structure type `Athanor`, Timer type `Moon Mining`, Objective `Neutral`, Owner name = their corp (free text), Solar system `Piekura`, Location = moon name, Date/time = the pop (EVE time), Visibility `Alliance`. Save.
3. It now sits on the same board as ours and gets the same 1-hour reminder and `@here` in `#moon-timers`.

Public timers don't self-renew: after the pop, delete or edit the timer for the next cycle.

## G. Backup and record (local session)

Say "run the backup script", then "commit the Day 5 config changes" — the deploy copies (`deploy/conf/requirements.txt`, `deploy/conf/local.py.append`) were already updated with this runbook; the local session only verifies the server matches.

## Day 5 completion checklist

- [ ] Holding-corp character registered on auth (A1)
- [ ] `#moon-timers` exists, two webhooks created and test messages received (A2–A3, C1)
- [ ] Three apps installed, migrations and data loads done, task queue drained (B)
- [ ] Two structuretimers rules: 60 min reminder, `@here` at pop (C2)
- [ ] Permissions set for the three groups (D)
- [ ] Athanor visible in Structures and Moon Mining; timer on the board; "Extraction started" in Discord (E)
- [ ] Backup taken (G)

## Troubleshooting

- **502 after `up -d`** → `docker compose restart nginx` (gunicorn got a new IP).
- **Add Owner refuses the character** → it must be registered on your auth account (A1) and hold the Director role in the owning corp. The holding-corp CEO always does; a second alt there needs Director (structures) and Station Manager (moonmining) assigned in game.
- **Extraction shows in Moon Mining but no timer / no Discord post** → the `MoonminingExtractionStarted` notification is older than what ESI still returns (it keeps a few days). The timer endpoint is still right; aa-structures will post *Finished*/*Fracture* when they happen, and the next extraction you schedule will post normally. Add this first one by hand (section F, step 2) if you want the reminder.
- **Discord post missing but admin → Structures → Notifications lists it as sent** → check the webhook URL; re-copy from Discord and paste again.
- **Test notification fails** → the channel's webhook was deleted, or the URL was pasted with a trailing space.
- **Tasks pile up in the queue** → normal during the map load; if still >0 an hour later, `docker compose logs --tail 50 allianceauth_worker` in the local session. (The queue is split by priority in redis, so `llen celery` alone reads 0; trust the dashboard's *Task Queue* panel, or have the local session sum all `celery*` list keys.)

**Next:** when the first chunk pops (Fri 16 Oct if scheduled as planned), check that `#moon-timers` got the reminder and the `@here`, and that Moon Mining → *Ledger* fills in once people mine. Then decide whether `aa-opcalendar` (pinned "upcoming events" embed) is worth adding.
