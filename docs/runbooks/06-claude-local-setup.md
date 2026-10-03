# Runbook — Claude Code on your PC with direct server access

*Why: the cloud sessions can only reach the internet over HTTPS, so they can never SSH to the server (verified 2026-10-03 with network access set to "Full"). Running Claude Code on your own PC removes that limit: it uses your PowerShell and your SSH key, and can run server commands itself.*

*Time: ~20 min, one-off. Needs: the `orlov-claude` key from runbook 05 B–C (already created and authorised on the server).*
*Status: **completed 2026-10-03** — local session verified, all 10 containers listed over `ssh orlov`.*
*Convention: one code block = one Enter.*

## A. Install Git for Windows (PowerShell, 3 min)

Claude Code needs `git` to work with the repo.

```powershell
winget install --id Git.Git -e --source winget
```

Close and reopen PowerShell afterwards, then:

```powershell
git --version
```

✅ Prints a version.

## B. Clone the repo to your PC (PowerShell, 2 min)

```powershell
git clone -b claude/orlov-alliance-auth https://github.com/Tony-carboni/Orlov.git "$HOME\Orlov"
```

If it asks you to sign in to GitHub, a browser window opens — sign in once; Git remembers it.

```powershell
dir "$HOME\Orlov"
```

✅ Shows `CLAUDE.md`, `docs`, `deploy`.

## C. Make the server reachable as `orlov` (PowerShell, 3 min)

An SSH config entry so that `ssh orlov` means "tony on 167.99.207.145 with the orlov-claude key" — short, and Claude doesn't need to know any of the details. **Paste as one block**:

```powershell
Add-Content -Path "$HOME\.ssh\config" -Value @"
Host orlov
    HostName 167.99.207.145
    User tony
    IdentityFile ~/.ssh/orlov-claude
    IdentitiesOnly yes
"@
```

Test:

```powershell
ssh orlov "hostname && docker compose -f ~/aa-docker/docker-compose.yml ps --format table"
```

✅ Prints the server's hostname and the container list, without asking for a passphrase.

## D. Start a LOCAL session in the Claude Code desktop app (5 min)

The desktop app can run a session in two places, and only one of them can reach the server:

| Session header shows | Where commands run | Server reachable? |
|---|---|---|
| ☁ cloud icon + `Orlov · Orlov` | a container in Anthropic's cloud | **no** (HTTPS-only) |
| 💻 laptop icon + a chip with the **folder name** (`Orlov`) | PowerShell on your PC | **yes** |

The chip shows the name of the folder the session was opened on. If it reads your user name (e.g. `Toon Budeners`) instead of `Orlov`, you opened the parent folder — start again and pick the `Orlov` subfolder.

Everything until now has been the cloud kind. To start the local kind:

1. If you don't have the app yet: download from https://claude.com/download, install, sign in with your claude.ai account.
2. **+ New** → do **not** pick the *Orlov* cloud environment; pick the **local / Open folder** option and choose `C:\Users\<you>\Orlov` (the clone from B).
3. Say: *"check server access"*. `CLAUDE.md` tells it to run `ssh orlov "..."`; it should show the container list.

✅ Done when the session header shows the laptop icon with an `Orlov` chip (no cloud icon) and Claude reports the containers from the server without you pasting anything.

## E. How to work from now on

- **Server work** (logs, restarts, config edits, Day 5 builds): in the **desktop app**, repo folder open. Claude runs the commands, shows the output, and still announces every state change before doing it (rules in `CLAUDE.md`).
- **Research, docs, planning**: either place. The cloud sessions keep working for anything that isn't the server.
- Both edit the same GitHub branch; whichever you used last, start the next session with *"pull the latest"* so the two stay in sync.

## F. Revoking Claude's server access (any time)

On the server:

```bash
sed -i '/orlov-claude/d' ~/.ssh/authorized_keys
```

Your own key (`id_ed25519`) is unaffected.
