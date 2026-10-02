# Runbook — giving Claude direct access to the server

*Goal: Claude (in these cloud sessions) can run commands on `167.99.207.145` itself — checks, log reads, config edits, container restarts — instead of handing you commands to paste. You still see everything it runs in the session.*

*Time: ~20 min, one-off. Afterwards every new session has access automatically.*
*Convention: one code block = one Enter.*

## How it works

- The cloud environment Claude runs in has a **network policy**; by default it blocks the server. You open it once.
- Claude logs in over SSH with its **own key**, not yours. You add that key's public half to the server, and keep the private half in the environment's settings so new sessions can find it. Nothing secret goes through the chat.
- You can revoke access at any moment by deleting one line on the server (section E).

## What you need
- Your PC with PowerShell (for `ssh-keygen` and `ssh`).
- The claude.ai session open (for the environment settings).
- Bitwarden.

---

## A. Open the network (claude.ai, 2 min)

1. In this session's title bar, open the **cloud environment** menu → **Edit**.
2. *Network access*: choose the **full / unrestricted** option. (The *Custom* allow-list works via an HTTPS proxy and does not carry SSH; full access is required for this.)
3. Save. Existing sessions pick it up on their next command.

Docs: https://code.claude.com/docs/en/cloud-environments#network-access

✅ Done when Claude's port test (`port 22 reachable`) passes — ask it to re-run it.

## B. Create a dedicated key on your PC (PowerShell, 2 min)

A key just for Claude, separate from yours, so it can be revoked on its own.

```powershell
ssh-keygen -t ed25519 -N '""' -C "orlov-claude" -f "$HOME\.ssh\orlov-claude"
```

(That `-N '""'` means "no passphrase" — required, since Claude can't type one.) Two files appear: `orlov-claude` (private) and `orlov-claude.pub` (public).

Show the public half:

```powershell
cat "$HOME\.ssh\orlov-claude.pub"
```

Copy the whole line (`ssh-ed25519 AAAA… orlov-claude`).

## C. Authorise the key on the server (PowerShell → server, 3 min)

```powershell
ssh tony@167.99.207.145
```

Then on the server — **paste the public-key line you copied inside the quotes**:

```bash
echo 'PASTE-THE-PUBLIC-KEY-LINE-HERE' >> ~/.ssh/authorized_keys
```

```bash
tail -2 ~/.ssh/authorized_keys
```

✅ The last line ends in `orlov-claude`. `exit` the server.

Test from your PC that the new key works on its own:

```powershell
ssh -i "$HOME\.ssh\orlov-claude" tony@167.99.207.145 "echo key-ok"
```

✅ Prints `key-ok` without asking for a passphrase.

## D. Store the private key for Claude (claude.ai + PowerShell, 5 min)

Claude's sessions are ephemeral; the key has to live in the environment settings.

1. Show the private key text on your PC:

```powershell
cat "$HOME\.ssh\orlov-claude"
```

   Select everything from `-----BEGIN OPENSSH PRIVATE KEY-----` to `-----END OPENSSH PRIVATE KEY-----` inclusive and copy it.
2. In this session's title bar → cloud environment menu → **Edit** → *Environment variables* → **Add**:
   - Name: `ORLOV_SSH_KEY`
   - Value: paste the key text (multi-line is fine).
   Save.
3. Also save the same text in Bitwarden as "orlov-claude SSH private key", then clear your clipboard.
4. Start a **new** session (environment variables are read at session start) and tell Claude: *"check server access"*. It will write the key to `~/.ssh/`, connect, and run `docker compose ps` for you.

✅ Done when Claude reports the container list from the server.

## E. Revoking access (any time, 1 min)

On the server:

```bash
sed -i '/orlov-claude/d' ~/.ssh/authorized_keys
```

And delete `ORLOV_SSH_KEY` from the environment settings. Claude is locked out immediately; your own key is unaffected.

## F. Ground rules for Claude once it has access (recorded in CLAUDE.md)

- Read-only first: `ps`, `logs`, `grep`, `df` freely.
- Anything that changes state (editing `conf/local.py` or `.env`, `restart`, `up -d`, migrations, backups) — say what and why in the chat before running it, one action at a time, and show the result.
- Never `rm -rf`, never touch `mysql-data/`, never run `do-release-upgrade`, never change `authorized_keys` or the firewall.
- Take a backup (`~/bin/aa-backup.sh`) before any migration or package change.
- Nothing from `.env` (tokens, passwords) is ever printed into the chat.
