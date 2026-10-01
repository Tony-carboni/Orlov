# Day 0 runbook — everything before the first `docker compose up`

*Goal of the day: by the end you own a server, a domain pointing at it, a Discord server with the right skeleton, an EVE developer app, a Discord bot, and a filled-in "secrets sheet". No Alliance Auth yet — that is Day 1.*

Time budget: ~4 hours of actual work, spread across the waiting times (DNS, server provisioning).

Do the steps **in this order**; later ones need values from earlier ones.

---

## Before you start: the secrets sheet

Install a password manager if you don't have one (Bitwarden is free). Create one entry called **"Orlov auth stack"** and, as you go, fill in these fields. Every value below is produced by one of the steps.

| Field | Produced in |
|---|---|
| VPS provider login | A1 |
| VPS public IPv4 | A4 |
| SSH private key location (file on your PC) | A2 |
| Sudo username + password on the VPS | A5 |
| Domain registrar login | B1 |
| Auth hostname (`auth.<yourdomain>`) | B2 |
| Discord server (guild) ID | C6 |
| Discord application ID | D2 |
| Discord OAuth2 client secret | D4 |
| Discord bot token | D3 |
| EVE SSO Client ID | E3 |
| EVE SSO Secret Key | E3 |
| Contact e-mail you'll give CCP (`ESI_USER_CONTACT_EMAIL`) | E3 |
| Your main character's name + character ID | E4 |

**Never** paste any of these into Discord, into this repo, or into a chat with anyone (including an AI assistant). They go in the password manager and later into a `.env` file on the server only.

---

## A. Server (VPS) — ~45 min, mostly waiting

### A1. Pick a provider and create an account
Any of these is fine technically; prices differ a lot for the same 2 vCPU / 4 GB box:

| Provider | Product name | Price (2 vCPU / 4 GB) |
|---|---|---|
| **Hetzner Cloud** (DE/FI/US) — recommended | *Server* → Shared vCPU → `CX22` | **~€4/mo** |
| Netcup / Contabo | VPS | €5–8/mo |
| DigitalOcean | *Droplet* → Basic → Regular → 4 GB | $24/mo |
| Vultr / Linode | Cloud Compute / Nanode | $20–24/mo |

Don't go below 4 GB RAM: the Alliance Auth stack (MariaDB, Redis, gunicorn, Celery workers, proxy, Grafana) won't fit in 1–2 GB.

Sign up, add a payment method, enable 2FA on the provider account.

### A2. Create an SSH key on your own computer
SSH keys replace passwords for logging into the server. You generate a pair once; the *public* half goes to the provider, the *private* half stays on your PC.

- **Windows 10/11**: open *PowerShell* and run
  ```powershell
  ssh-keygen -t ed25519 -C "orlov-vps"
  ```
  Press Enter to accept the default path (`C:\Users\<you>\.ssh\id_ed25519`), and set a passphrase (write it in the secrets sheet).
- **macOS / Linux**: same command in Terminal; default path `~/.ssh/id_ed25519`.

Then show the public key and copy the whole line (starts with `ssh-ed25519`):
```powershell
cat ~/.ssh/id_ed25519.pub
```

### A3. Add the SSH key to the provider
In the provider's web console: *Security → SSH keys → Add* → paste the public key → name it.

### A4. Create the server
- Image/OS: **Ubuntu 24.04 LTS**
- Size: 2 vCPU / 4 GB RAM / ≥40 GB disk
- Location: closest to most of your members (EVE runs in London; EU is a fine default)
- SSH key: the one from A3 (do **not** choose password login)
- Name: `orlov-auth`
- Provider firewall (if offered): allow inbound TCP **22, 80, 443** only.

Wait for it to come up; copy the **public IPv4 address** into the secrets sheet.

### A5. First login and basic hardening (copy-paste block)
From PowerShell / Terminal:
```bash
ssh root@<VPS-IP>
```
(Type `yes` at the fingerprint prompt; enter your key passphrase.)

Now, on the server, run these one block at a time:

```bash
# 1. updates
apt update && apt -y upgrade

# 2. a normal user with sudo (replace 'tony' with the username you want)
adduser tony            # choose a password, store it in the secrets sheet; press Enter through the questions
usermod -aG sudo tony
rsync --archive --chown=tony:tony ~/.ssh /home/tony   # copies your SSH key to the new user

# 3. firewall
apt -y install ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# 4. automatic security updates
apt -y install unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades   # choose <Yes>

# 5. disable root SSH login and passwords
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

**Open a second terminal and test before closing the first one:**
```bash
ssh tony@<VPS-IP>
sudo -v     # asks your password; no error = sudo works
```
If that works, close the root session. From now on always log in as `tony`.

### A6. Install Docker
Still as `tony` on the server:
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
sudo apt -y install git curl
exit
```
Log in again (`ssh tony@<VPS-IP>`) so the group change applies, then verify:
```bash
docker --version
docker compose version
docker run --rm hello-world     # should print "Hello from Docker!"
```

✅ **A done when:** you can `ssh tony@<VPS-IP>` with your key and `docker compose version` prints a version.

---

## B. Domain and DNS — 15 min + up to an hour of propagation

### B1. Buy a domain
Any registrar; **Porkbun**, **Cloudflare Registrar** or **Namecheap** are cheap and sane. Pick something short the alliance will keep (`<alliance>.space`, `.gg`, `.org`…). Enable 2FA on the registrar account.

### B2. Create the DNS record
In the registrar's DNS panel add:

| Type | Name/Host | Value | TTL |
|---|---|---|---|
| `A` | `auth` | `<VPS-IP>` | Auto / 300 |

If the panel is Cloudflare: set the orange cloud to **grey (DNS only)** for this record — it keeps certificate issuance simple on Day 1.

Your auth hostname is now `auth.<yourdomain>` → write it in the secrets sheet.

### B3. Verify
From your PC (may take 5–60 min to work):
```powershell
nslookup auth.<yourdomain>
```
It must answer with the VPS IP.

✅ **B done when:** `nslookup` returns your VPS IP.

---

## C. Discord server — 45 min

You can reuse an existing server, but a fresh one is cleaner because the permission model below assumes nothing has been granted yet.

### C1. Enable Developer Mode (needed to copy IDs)
Discord → *User Settings (gear) → Advanced → Developer Mode: ON*.
Also: *User Settings → My Account →* enable **2FA** on your own Discord account (server moderation features and the bot setup assume it).

### C2. Create the server
"+" in the server list → *Create My Own* → *For a club or community* → name it after the alliance → upload the alliance logo later.

### C3. Create roles (Server Settings → Roles)

Roles as created on 2026-10-01. Names are **case-sensitive and must match Alliance Auth state/group names exactly**, so don't rename casually.

| Role (top → bottom order in the list) | Who gets it | Managed by (AA side) |
|---|---|---|
| *(bot role — appears automatically when the bot joins on Day 1; drag it to the very top then)* | the bot | Discord |
| `Alliance Director` | alliance leadership | manual group `Alliance Director` |
| `Corp Director` | directors/CEOs of member corps | manual group `Corp Director` (later: auto from in-game Director role) |
| `FC` | fleet commanders | request group `FC` |
| `Family Member` | every alliance member | **state** `Family Member` — AA syncs the state name as a role |
| `Family Friend` | allied / blue pilots | **state** `Family Friend` |
| `corp_<TICKER>` — one per member corp, e.g. `corp_OARMI` | members of that corp | AA auto-group: prefix `corp_`, source = ticker |
| `@everyone` | unauthenticated people | — |

Role settings: for all of them *Allow anyone to @mention this role: OFF*. *Display separately* ON for `Alliance Director`, `Corp Director`, `FC`, `Family Member`.

When a new corp joins: create `corp_<TICKER>` here; AA creates the matching auto-group on its own.

### C4. Lock down `@everyone`
*Server Settings → Roles → @everyone → Permissions*: turn **OFF** *View Channels*, *Send Messages*, *Connect*, *Create Invite*, *Change Nickname*. Save. This makes the server invisible to anyone who hasn't authenticated, except where we explicitly allow it.

### C5. Create the channel skeleton
Create categories and channels; the permissions column is what you set on the **category** (channels inherit).

| Category | Channels | Permissions |
|---|---|---|
| `WELCOME` | `#how-to-auth` (text), `#rules` (text) | `@everyone`: View Channel ✅, Read History ✅, Send Messages ❌ |
| `ALLIANCE` | `#announcements`, `#general`, `#fleet-pings`, `#intel`, `#market-industry` | `Family Member`: View ✅ Send ✅ ; `Family Friend`: View ✅ on `#general` and `#fleet-pings` only |
| `LEADERSHIP` | `#directors`, `#corp-directors`, `#fc-chat` | `Alliance Director` ✅ all; `Corp Director` on `#corp-directors`; `FC` on `#fc-chat`; everyone else ❌ |
| `VOICE` | `Fleet 1`, `Fleet 2`, `Lounge` | `Family Member`: View ✅ Connect ✅ Speak ✅ ; `Family Friend`: `Fleet 1/2` only |
| `BOT` | `#auth-log`, `#bot-commands` | `Alliance Director`: View ✅; later the AA bot posts here |

In `#how-to-auth` post a placeholder message now: "Authentication opens on <date>. You will log in with your EVE account at https://auth.<yourdomain> and link Discord from there." You'll replace it on Day 2.

### C6. Copy the server ID
Right-click the server icon → **Copy Server ID** → secrets sheet (this is `DISCORD_GUILD_ID`).

### C7. Create an invite link
Right-click `#how-to-auth` → *Invite People* → *Edit invite link* → **Expire: never**, **Max uses: no limit** → copy. This is the only link you ever hand out; people arrive seeing just the welcome channels until they auth.

✅ **C done when:** a fresh account joining via the invite sees only `#how-to-auth` and `#rules`.

---

## D. Discord application (the bot) — 15 min

### D1. Create the application
<https://discord.com/developers/applications> → *New Application* → name: `<Alliance> Auth` → agree → *Create*.

### D2. General Information tab
Copy **Application ID** → secrets sheet (`DISCORD_APP_ID`). Add the alliance logo as the icon if you like.

### D3. Bot tab
- *Reset Token* → confirm → **copy the token now** (it is shown exactly once) → secrets sheet (`DISCORD_BOT_TOKEN`). If you lose it, come back and reset again.
- *Public Bot*: **OFF** (only you can add it to servers).
- *Requires OAuth2 Code Grant*: OFF.
- *Privileged Gateway Intents*: turn **ON** *Server Members Intent* and *Message Content Intent* (the latter is needed by `aa-discordbot` in Phase 4). *Presence Intent* ON too — harmless and the discordbot wants it.
- Save.

### D4. OAuth2 tab
- *Client Secret* → *Reset Secret* → copy → secrets sheet (`DISCORD_APP_SECRET`).
- *Redirects* → *Add Redirect* → enter **exactly** (including the trailing slash):
  ```
  https://auth.<yourdomain>/discord/callback/
  ```
  Save changes.

You do **not** add the bot to the server today; Alliance Auth generates the correct invite with the right permissions on Day 2.

✅ **D done when:** the secrets sheet has Application ID, client secret and bot token, and the redirect is saved.

---

## E. EVE Online developer application — 15 min

### E1. Log in to the developer portal
<https://developers.eveonline.com/> → *Log in* with the EVE account that owns your main character.

> Requirement: the account must have been **Omega at some point** (CCP gates app creation on having paid once). If the portal refuses to let you create an application, that's why — use your main account.

Accept the Developer Licence Agreement when prompted.

### E2. Create the application
*Manage Applications → Create New Application*:
- **Name:** `<Alliance> Auth` (members will see this name on the "authorize" screen).
- **Description:** "Alliance authentication and member management for <Alliance>."
- **Connection type:** *Authentication & API Access* (not "Authentication only").
- **Permissions / scopes:** tick **`publicData`** and **all `esi-*` scopes**. Rationale: the app's scope list is the *maximum* it may ever request; Alliance Auth only asks members for the subset a given feature needs. Ticking everything now means you never have to come back here when installing a plugin.
- **Callback URL:** exactly
  ```
  https://auth.<yourdomain>/sso/callback
  ```
  (no trailing slash — this is what Alliance Auth's docs specify).
- Create.

### E3. Copy the credentials
On the application's page copy **Client ID** and **Secret Key** → secrets sheet (`ESI_SSO_CLIENT_ID`, `ESI_SSO_CLIENT_SECRET`). Decide which e-mail address CCP may use to contact you about your app → `ESI_USER_CONTACT_EMAIL`.

### E4. Note your main character's ID
Open <https://zkillboard.com/> and search your character; the number in the URL (`/character/<id>/`) is the character ID. Secrets sheet. (Useful on Day 1 to attach the superuser.)

✅ **E done when:** Client ID + Secret in the sheet; callback shows `https://auth.<yourdomain>/sso/callback`.

---

## F. Membership design worksheet — 30 min, no computer needed

Fill this in; it becomes the Alliance Auth configuration on Day 2. Keep it in `docs/design/membership.md` in this repo (no secrets in it).

### F1. Entities
| Entity | Type | ID | Ticker |
|---|---|---|---|
| Your alliance | alliance | *(when created)* | |
| Member corp 1 | corporation | *(zkillboard URL)* | OARMI |
| … | | | |
| Allied alliance (blue) 1 | alliance | | |

(Until the alliance exists in-game, list your executor corp; AA can be switched to the alliance ID the day the alliance is created.)

### F2. States (mutually exclusive, highest priority wins)
| State | Priority | Qualifies if main character is in… | Discord role (same name, synced by AA) |
|---|---|---|---|
| `Family Member` | 100 | the alliance (today: corp OARMI) | `Family Member` |
| `Family Friend` | 50 | listed allied alliances/corps | `Family Friend` |
| `Guest` | — | anything else (built in) | none — removed from server |

### F3. Groups → Discord roles
| AA group | Type | Discord role | Who grants |
|---|---|---|---|
| `corp_<TICKER>` | auto-group (prefix `corp_`, ticker) | `corp_<TICKER>` | AA |
| `Alliance Director` | manual, hidden | `Alliance Director` | you, in AA admin |
| `Corp Director` | manual, hidden (later: auto from ESI corp roles) | `Corp Director` | you / corp CEOs |
| `FC` | request + approval | `FC` | FC lead |

### F4. Policies to decide now (write one sentence each)
1. Must members register **all** characters, or only their main? (Member Audit compliance depends on this.)
2. After how many days without login is a member "inactive"? What happens then?
3. Is fleet participation (PAP) tracked, and is there a monthly minimum?
4. Who in each corp is responsible for adding the Director token (CEO? any director?)
5. Nickname format on Discord: `Character Name` or `[TICKER] Character Name`?

---

## Day 0 completion checklist

- [ ] A: `ssh tony@<ip>` works with key; `docker compose version` works; root login disabled
- [ ] B: `nslookup auth.<domain>` returns the VPS IP
- [x] C3: roles created (`Alliance Director`, `Corp Director`, `FC`, `Family Member`, `Family Friend`, `corp_OARMI`)
- [ ] C: `@everyone` locked down, channels, invite link saved, server ID in sheet
- [ ] D: Discord app with bot token, client secret, redirect `https://auth.<domain>/discord/callback/`
- [ ] E: EVE app with all scopes, callback `https://auth.<domain>/sso/callback`, Client ID + Secret in sheet
- [x] F: membership worksheet filled in and committed to `docs/design/membership.md` (2026-10-01)
- [ ] Secrets sheet complete in the password manager; nothing secret in git or Discord

**Next:** Day 1 runbook — deploying Alliance Auth (`docs/runbooks/01-day-one-deploy-aa.md`).
