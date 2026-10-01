# Day 2 runbook — states, groups and the Discord bot

*Prerequisite: Day 1 complete — https://auth.orlovfamily.space works, you're logged in as superuser `tony` with your main character set.*
*Time: ~1.5 hours. Sections A–B on the server; C–F in the browser.*

Goal of the day: logging into auth as an OARMI pilot yields state `Family Member` + group `corp_OARMI`, and activating Discord on the Services page puts the matching roles on the person in the Discord server.

---

## A. Add the Discord secrets to `.env` (server)

From Bitwarden you need: Discord **Server ID**, **Application ID**, **Client Secret**, **Bot Token**.

```bash
cd ~/aa-docker
nano .env
```

Go to the very end (Ctrl+End) and add four lines, with your real values:

```
# Discord
DISCORD_GUILD_ID=123456789012345678
DISCORD_APP_ID=123456789012345678
DISCORD_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DISCORD_BOT_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx.xxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

No quotes, no spaces around `=`. Ctrl+O, Enter, Ctrl+X.

## B. Enable the apps in `local.py` and restart (server)

Uncomment the two built-in apps and append our block (copy-paste the whole thing as one):

```bash
cd ~/aa-docker
sed -i "s/^    # 'allianceauth.corputils',/    'allianceauth.corputils',/; s/^    # 'allianceauth.services.modules.discord',/    'allianceauth.services.modules.discord',/" conf/local.py
grep -nE "corputils|modules.discord" conf/local.py
```

Both lines must now show **without** the `#`. Then append the custom block:

```bash
cat >> conf/local.py <<'PYEOF'

#######################################
# The Orlov Family — custom settings  #
#######################################

INSTALLED_APPS += [
    "allianceauth.eveonline.autogroups",   # corp_<TICKER> groups
]

# --- Discord service -------------------------------------------------------
DISCORD_CALLBACK_URL = f"{SITE_URL}/discord/callback/"  # Do NOT change this line!
DISCORD_GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "")
DISCORD_APP_ID = os.environ.get("DISCORD_APP_ID", "")
DISCORD_APP_SECRET = os.environ.get("DISCORD_APP_SECRET", "")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
DISCORD_SYNC_NAMES = True

CELERYBEAT_SCHEDULE["discord.update_all_usernames"] = {
    "task": "discord.update_all_usernames",
    "schedule": crontab(minute="0", hour="*/12"),
}

# --- Corp Stats ------------------------------------------------------------
CELERYBEAT_SCHEDULE["update_all_corpstats"] = {
    "task": "allianceauth.corputils.tasks.update_all_corpstats",
    "schedule": crontab(minute="0", hour="*/6"),
}
PYEOF
tail -5 conf/local.py
```

Restart the auth containers (they must be *recreated* to pick up the new `.env` values) and run the Django maintenance:

```bash
docker compose --env-file=.env up -d --force-recreate allianceauth_gunicorn allianceauth_beat allianceauth_worker allianceauth_worker_services
docker compose exec allianceauth_gunicorn bash
```
inside the container:
```bash
auth migrate
auth collectstatic --noinput
exit
```
back on the host:
```bash
docker compose ps | grep -E "gunicorn|beat|worker"
```

✅ All four Up. If gunicorn is restarting: `docker compose logs allianceauth_gunicorn --tail 40` — a typo in `local.py` shows up here as a Python error with a line number.

## C. States (browser)

Go to **https://auth.orlovfamily.space/admin/** → *Authentication* → **States**. You'll see `Guest` and `Member`.

1. Click **Member** and rename it: Name `Family Member`, Priority `100`. In **Member corporations** pick **Orlov Arms International** (it's in the list because your main is in it). Leave *Member alliances* empty until the alliance exists. Under **Permissions**, find and add `discord | user | Can access the Discord Service` (search box: type `access_discord`). **Save**.
2. **Add State**: Name `Family Friend`, Priority `50`, no corporations/alliances yet, permission `discord | user | Can access the Discord Service`. **Save**.
3. Leave `Guest` as is.

Reload the dashboard (https://auth.orlovfamily.space/) — your state now shows **Family Member**.

## D. Auto-groups and manual groups (browser)

**Auto-groups** — `/admin/` → *Eve_Autogroups* → **Autogroups configs → Add**:

| Field | Value |
|---|---|
| States | `Family Member` (and `Family Friend`) |
| Corp groups | ☑ |
| Corp group prefix | `corp_` |
| Corp name source | **Ticker** |
| Alliance groups | ☐ (the state already covers it) |
| Replace spaces | ☐ |

**Save.** The prefix/name-source can't be changed afterwards (you'd delete and recreate the config). Check *Authentication → Groups*: `corp_OARMI` should exist with you in it. If it doesn't appear within a minute, open your user in *Authentication → Users*, and Save without changes — that re-triggers group evaluation.

**Manual groups** — *Authentication* → **Groups → Add group**, three times:

| Name | Settings (the "Auth group" box on the same page) |
|---|---|
| `Alliance Director` | Internal ☑ (only admins assign it) |
| `Corp Director` | Internal ☑ |
| `FC` | Internal ☐, Hidden ☐, Open ☐ → members can *request*, a group leader or you approve |

Then add yourself to `Alliance Director`: *Users → tony → Groups*, move it to "Chosen", Save.

✅ Dashboard → *Groups* shows `corp_OARMI` and `Alliance Director` on you.

## E. Link the bot and test (browser + Discord)

1. In Discord, make sure **your own account has 2FA enabled** (User Settings → My Account). Discord refuses role/kick operations by bots whose owner lacks it.
2. auth → top menu **Services**. Click the green **Link Discord Server** button → Discord asks which server → pick *The Orlov Family* → **Authorize**. The bot joins; a new role named after your Discord application appears.
3. In Discord: *Server Settings → Roles* → drag the **bot's role to the very top**, above `Alliance Director`. Every time the bot is re-added you must do this again.
4. Back on **Services**: the Discord row now has an **Activate** (✓) button. Click it → Discord OAuth → **Authorize**. You're redirected back; the row shows your Discord username.
5. In Discord, look at yourself in the member list: roles `Family Member`, `corp_OARMI`, `Alliance Director` should be there, and (if you are **not** the server owner) your nickname is your character name.

Known limitation: Discord never lets a bot change the **server owner's** nickname, so for you specifically nickname sync logs an error and you set it by hand (`[OARMI] Character Name`). Everyone else gets it automatically. If that bothers you later, transfer server ownership to a throwaway "holding" account — that's what the AA docs recommend.

6. Test role removal: in `/admin/`, remove yourself from `Alliance Director`, Save, wait ~30 s → the role disappears in Discord. Add it back.

## F. Corp Stats (browser)

auth → **Corporation Stats** (left menu) → **Add** → EVE SSO (it asks for the `read_corporation_membership` scope) → Authorize with your main (any OARMI member works for this one; director tokens come in Phase 4). You get the OARMI member list, split into *registered* / *unregistered* — this is your "who hasn't authed yet" view. It refreshes every 6 h.

---

## Day 2 completion checklist

- [ ] Dashboard shows state `Family Member`, groups `corp_OARMI` + `Alliance Director`
- [ ] Bot in the server, its role at the top of the list
- [ ] Services → Discord activated; roles appear on you in Discord; removal test worked
- [ ] Corp Stats for OARMI shows the member list
- [ ] Fresh DB dump: `cd ~/aa-docker && docker compose exec -T auth_mysql sh -c 'exec mariadb-dump --all-databases -uroot -p"$MYSQL_ROOT_PASSWORD"' | gzip > ~/backups/aa-$(date +%F).sql.gz`

**Next:** rollout — have 2–3 trusted OARMI members go through *log in → Add Character → Services → Discord* and watch the roles land. Then Phase 4 (Member Audit, discordbot with `[OARMI]` nicknames).

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Unknown Error" on the Discord site when activating | Redirect in Discord developer portal must be exactly `https://auth.orlovfamily.space/discord/callback/` — trailing slash. |
| Activated, but no roles appear | Bot role not at the top; or the role names differ (`Family Member` ≠ `family member`? AA matches case-insensitively, but check for stray spaces); check *Notifications* (bell icon) in auth for the error text. |
| Roles for other bots keep getting removed | `/admin/` → *Group Management → Reserved group names* → add those role names. |
| `corp_OARMI` never appears | Autogroups config states must include `Family Member`; re-save your user to trigger. |
| Nickname errors for you only | You're the server owner — expected (see E). |
