# Day 2 runbook — states, groups and the Discord bot

*Prerequisite: Day 1 complete — https://auth.orlovfamily.space works, you're logged in as superuser `tony` with your main character (Orlov Arms International) set.*
*Time: ~1.5 hours. Sections A–B on the **server**; C–F in the **browser**.*
*Convention: **one code block = one Enter**. Blocks that must be pasted whole are labelled.*

**Goal:** logging into auth as an OARMI pilot yields state `Family Member` + group `corp_OARMI`, and activating Discord on the Services page puts the matching roles on that person in the Discord server.

## Known values

| Item | Value |
|---|---|
| Server | `ssh tony@167.99.207.145` → stack in `~/aa-docker` |
| Auth site | https://auth.orlovfamily.space |
| Admin site | https://auth.orlovfamily.space/admin/ (login `tony` + Django admin password, or just be logged in via SSO as `tony`) |
| Discord redirect (already set on Day 0) | `https://auth.orlovfamily.space/discord/callback/` |
| Corp | Orlov Arms International — `OARMI` |
| States to end with | `Family Member` (100), `Family Friend` (50), `Guest` (built in) |
| Groups to end with | `corp_OARMI` (automatic), `Alliance Director`, `Corp Director`, `FC` |
| Discord roles (exist since Day 0) | `Alliance Director`, `Corp Director`, `FC`, `Family Member`, `Family Friend`, `corp_OARMI` |

**From Bitwarden, have ready:** Discord *Server ID*, Discord *Application ID*, Discord *Client Secret*, Discord *Bot Token*.

---

## A. Add the Discord secrets to `.env` (server)

```bash
ssh tony@167.99.207.145
```
then:
```bash
cd ~/aa-docker
nano .env
```

Ctrl+End to jump to the bottom, then type/paste (right-click pastes in PowerShell) these four lines with your real values — no quotes, no spaces around `=`:

```
# Discord
DISCORD_GUILD_ID=<Server ID, 18–19 digits>
DISCORD_APP_ID=<Application ID, 18–19 digits>
DISCORD_APP_SECRET=<Client Secret, 32 characters>
DISCORD_BOT_TOKEN=<Bot Token, ~72 characters with two dots>
```

Ctrl+O, Enter, Ctrl+X. Verify the four keys exist (values hidden):

```bash
grep -E '^DISCORD_' .env | sed 's/=.*/=<set>/'
```

✅ Four lines: `DISCORD_GUILD_ID=<set>` … `DISCORD_BOT_TOKEN=<set>`.

## B. Enable the apps in `local.py`, check, restart (server)

**B1. Uncomment the two built-in apps:**

```bash
cd ~/aa-docker
grep -nE "corputils|modules.discord" conf/local.py
```

This prints two line numbers (upstream file as of v5.4.0: **64** and **71**). Remove the `# ` on exactly those lines — adjust the numbers if yours differ:

```bash
sed -i '64s/# //; 71s/# //' conf/local.py
grep -nE "corputils|modules.discord" conf/local.py
```

✅ Both lines print **without** a `#`.

**B2. Append the Orlov settings** — **paste as one block** (it ends at `PYEOF`):

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
DISCORD_SYNC_NAMES = False  # True breaks activation for the server owner (403)

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
tail -3 conf/local.py
```

✅ The last lines show the `update_all_corpstats` block closing with `}`.

**B3. Recreate the auth containers** (needed so they read the new `.env`), then validate and migrate inside:

```bash
docker compose --env-file=.env up -d --force-recreate allianceauth_gunicorn allianceauth_beat allianceauth_worker allianceauth_worker_services
docker compose exec allianceauth_gunicorn bash
```
inside the container (prompt `allianceauth@…:~/myauth$`):
```bash
auth check
auth migrate
auth collectstatic --noinput
exit
```

`auth check` must say **"System check identified no issues"**. If it prints a Python traceback instead, the line number points at a typo in `conf/local.py`; fix with `nano conf/local.py` on the host and re-run from B3.

```bash
docker compose ps | grep -E "gunicorn|beat|worker"
```

✅ All four `Up`. Open https://auth.orlovfamily.space — the left menu now has **Services** and **Corporation Stats**.

## C. States (browser)

Open **https://auth.orlovfamily.space/admin/authentication/state/** — you see `Guest`, `Member` and `Blue`.

**C1.** Click **Member** and change it:

| Field | Value |
|---|---|
| Name | `Family Member` |
| Priority | `100` |
| Member characters | leave empty |
| Member corporations | move **Orlov Arms International** to *Chosen* |
| Member alliances | move **The Orlov Family** to *Chosen* |
| Member factions | leave empty |
| Permissions | type `access_discord` in the filter box → move **discord \| user \| Can access the Discord Service** to *Chosen* |
| Public | ☐ |

**Save.**

**C2.** Click **Blue** (AA's built-in "allies" state) and rename it the same way:

| Field | Value |
|---|---|
| Name | `Family Friend` |
| Priority | `50` (already) |
| Member corporations/alliances | empty for now |
| Permissions | `discord | user | Can access the Discord Service` |

**Save.** Leave `Guest` untouched.

✅ Reload https://auth.orlovfamily.space/ — the dashboard shows **State: Family Member**.

## D. Groups (browser)

**D1. Auto-groups** — open **https://auth.orlovfamily.space/admin/eve_autogroups/autogroupsconfig/add/**:

| Field | Value |
|---|---|
| States | move `Family Member` and `Family Friend` to *Chosen* |
| Corp groups | ☑ |
| Corp group prefix | `corp_` |
| Corp name source | **Ticker** |
| Alliance groups | ☐ |
| Alliance group prefix / name source | leave default |
| Replace spaces | ☐ |

**Save.** Prefix and name source are locked after saving — if you got them wrong, delete the config and add a new one.

**D2. Manual groups** — open **https://auth.orlovfamily.space/admin/groupmanagement/group/add/** three times. The page has *Name* + *Permissions* at the top and an **Auth group** box below with the AA flags:

| Name | Internal | Hidden | Open | Public |
|---|---|---|---|---|
| `Alliance Director` | ☑ | ☐ | ☐ | ☐ |
| `Corp Director` | ☑ | ☐ | ☐ | ☐ |
| `FC` | ☐ | ☐ | ☐ | ☐ |

(Internal = only admins assign it. `FC` with everything off = members can request it on the Groups page and you approve.)

**D3. Put yourself in the leadership groups.** Groups don't nest — you get exactly the Discord roles of the groups you're in — so as alliance executor, OARMI CEO and FC, add `tony` to all three: admin → Group Management → Groups → open `Alliance Director` → *Chosen Users* → add `tony` → **Save**; repeat for `Corp Director` and `FC`.

✅ Open **https://auth.orlovfamily.space/admin/groupmanagement/group/** — `corp_OARMI` is listed (created automatically) alongside your three. To see your own memberships: admin → *Authentication → Users → tony → Groups* (the 5.4 dashboard does not list groups). If `corp_OARMI` is missing after a minute, open your user in admin and Save it without changes — that re-runs the auto-group evaluation.

## E. Link the bot and test (browser + Discord)

**E1.** In Discord → *User Settings → My Account*: make sure **2FA is enabled on your account** (the bot belongs to you; Discord blocks role/kick operations by bots whose owner lacks 2FA).

**E2.** auth → left menu **Services** → on the Discord card click the **🔗 link icon** (this is "Link Discord Server") → Discord asks which server → choose your alliance server → **Authorize**. The bot joins the server; a new role with your Discord application's name appears.

**E3.** In Discord → *Server Settings → Roles* → drag the **bot's role to the very top**, above `Alliance Director`. (Repeat whenever the bot is re-added.)

**E4.** Back on **Services** → Discord card → the orange **✓** (Activate) → Discord OAuth → **Authorize**. You're sent back; the row now shows your Discord username.

**E5.** In Discord, click yourself in the member list. Expected roles: `Family Member`, `corp_OARMI`, `Alliance Director`, `Corp Director`, `FC`. Nickname unchanged (see note below).

> **Server-owner note:** Discord never lets a bot change the **owner's** nickname. With `DISCORD_SYNC_NAMES = True`, AA sends nickname + roles in one request and the owner's activation fails with 403 "Missing Permissions" — which is why it's `False` in B2. Nicknames (`[OARMI] Character Name`) come from discordbot in Phase 4, which handles the owner gracefully.

**E6. Removal test:** admin → Group Management → Groups → `FC` → remove `tony` from *Chosen Users* → Save. Within ~30 s the `FC` role vanishes in Discord. Add it back and Save.

✅ Roles appear and disappear in Discord without touching Discord.

## F. Corp Stats (browser)

Open **https://auth.orlovfamily.space/corpstats/** → **Add** → EVE SSO asks for the `read_corporation_membership` scope → authorize with your main. You now see OARMI's member list split into **registered** (have an auth account) and **unregistered** (red) — your "who hasn't authed yet" view. It refreshes every 6 h; the *Update* button forces it.

---

## Day 2 completion checklist

- [ ] State `Family Member`; groups `corp_OARMI`, `Alliance Director`, `Corp Director`, `FC`
- [ ] Bot in the Discord server, its role at the top
- [ ] Services → Discord activated; roles on you; removal test passed
- [ ] Corp Stats for OARMI loads
- [ ] Fresh DB dump (server) — three blocks, one Enter each:
  ```bash
  cd ~/aa-docker
  ```
  ```bash
  docker compose exec -T auth_mysql sh -c 'exec mariadb-dump --all-databases -uroot -p"$MYSQL_ROOT_PASSWORD"' | gzip > ~/backups/aa-$(date +%F).sql.gz
  ```
  ```bash
  ls -lh ~/backups
  ```

**Next:** have 2–3 trusted OARMI members do *log in with EVE → Add Character → Services → Discord → Activate* and confirm their roles land. Then Phase 4: `aa-memberaudit` and `allianceauth-discordbot` (incl. `[OARMI]` nicknames).

## Day-to-day: how people get leadership roles from now on

**`FC` (requestable):** member → auth → *Groups* → **Request** on `FC` → status "Pending", nothing changes yet. You (or a *group leader* you assign on the `FC` group in admin, e.g. the FC lead) → *Group Management → Requests* → **Accept**/**Reject**. On accept, the `FC` role and `#fc-chat` appear in Discord within ~30 s. Remove via *Group Management → Members*.

**`Corp Director` / `Alliance Director` (internal):** members can't see or request these. You add/remove people in admin → Group Management → Groups → the group → *Chosen Users*. Discord follows automatically. (Phase 4 option: fill `Corp Director` automatically from the in-game Director role once corp tokens exist.)

**Always automatic:** leaving the alliance drops the state to `Guest`, which strips every group and Discord role. Roles only apply to people who have linked Discord on the Services page.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `auth check` traceback | Typo in the appended block; the message names the line. `nano conf/local.py`, fix, re-run B3. |
| Services page has no Discord row | `modules.discord` still commented out (B1), or containers weren't recreated (B3). |
| "Unknown Error" on Discord when activating | Redirect in the Discord developer portal must be exactly `https://auth.orlovfamily.space/discord/callback/` — trailing slash. |
| Activated but no roles | Bot role not at the top of the role list; or your Discord account lacks 2FA. Check auth's **Notifications** (bell icon) for the error text. |
| Roles from other bots keep disappearing | admin → *Group Management → Reserved group names* → add those role names. |
| `corp_OARMI` never appears | Autogroups config must list `Family Member` under States; re-save your user. |
| Activation fails with 403 "Missing Permissions" for you | `DISCORD_SYNC_NAMES` is `True` and you're the server owner. Set it to `False` in `conf/local.py`, `docker compose restart allianceauth_gunicorn`, retry. |
| Need logs | `docker compose logs -f --tail 100 allianceauth_worker` (Ctrl+C to stop) — Discord tasks run in the workers. |
