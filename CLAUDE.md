# Orlov — project notes for Claude

## What this repo is
Documentation and deployment config for **The Orlov Family** (EVE Online alliance, ticker ORLOV; executor corp Orlov Arms International, OARMI) member-management platform, built on **Alliance Auth** (Docker) with Discord role sync.

- `docs/research/` — why Alliance Auth was chosen over SeAT/Neucore, the phased plan, moon timers, corp industry/projects mechanics (`04`), and the ship-building dashboard plan (`05`)
- `docs/design/membership.md` — states, groups → Discord roles, policies (source of truth for AA config)
- `docs/runbooks/` — step-by-step, beginner-level runbooks (`00` Day 0 prep, `01` deploy, `02` membership + Discord, `03` nicknames + Member Audit, `04` operations, `05` cloud SSH attempt — superseded, `06` Claude Code on the PC with server access, `07` Day 5 moon timers, `08` Day 6 `/moons` slash command, `09` moon board in Discord, `10` structure board in Discord, `11` kill feed in `#zkillboard`, `12` jump freighter watch in `#jf-gank-board`, `13` Shipyard plugin private test release, `14` Shipyard front door at `shipyards.orlovfamily.space`)
- `docs/guides/` — documents for other people: the member guide (for `#how-to-auth`) and the corp CEO onboarding checklist
- `docs/handoff.md` — shared notebook between the cloud and local session (see "Session handoff")
- `apps/shipyard/` — the **Shipyard** Alliance Auth plugin (Python/Django, pip-installable from the repo archive); its README documents it
- `deploy/` — what differs from the upstream `aa-docker` stack on the server (sanitized; no secrets)

The owner is new to servers/Docker/Linux: write runbooks as copy-paste blocks, say which machine each command runs on (PC `PS C:\` vs server `tony@ubuntu…:~$`), and give an "✅ done when" check per section.

**Command blocks: one code block = one Enter — in runbooks *and* in chat replies.** Put each command in its own fenced block, never several commands in one block, so the copy button yields exactly one command. A block that genuinely spans lines (a heredoc, a long `docker compose` invocation) is labelled "paste as one block". Keep single commands short enough not to need wrapping; split long argument lists into separate commands where possible. Reason: the owner pastes into PowerShell, where a wrapped line and two lines look identical. **Never put non-commands (file previews, expected output, YAML snippets) in a fenced block** — every fenced block gets pasted into the terminal. Describe expected output in prose or a table instead.

## Reply style when the owner shares terminal output or screenshots
- Everything fine → confirm in one line and name the next step (e.g. "Step B looks good, continue with C").
- Something wrong → say what, why, and give the exact fix, one command per block.
- Don't restate what went right in detail; the owner wants to keep moving.
- When pointing to the next runbook step, name it ("continue with D2") — don't summarize its contents; the owner has the runbook open alongside.

## Branch naming
Use **descriptive, human-readable branch names**, never auto-generated ones like `claude/determined-pasteur-1denoh`.

- Pattern: `claude/<topic-in-kebab-case>`, e.g. `claude/orlov-alliance-auth`, `claude/day-3-member-audit`, `claude/discordbot-nicknames`.
- If a session is started on an auto-generated branch name, rename it to a descriptive one at the start of the work (`git branch -m <old> <new>`, push the new name, tell the user) rather than carrying the random name forward.
- Same rule for anything else that gets a name the user will see later: files, docs, commit subjects.

## Server access
Cloud sessions **cannot** reach the server (HTTPS-only egress, verified 2026-10-03 even with network access "Full") — don't try; say so and hand server work to a local session.
In a **local session** (Claude Code desktop/CLI on the owner's Windows PC, set up per `docs/runbooks/06-claude-local-setup.md`), the server is reachable as `ssh orlov "<command>"` (alias in `~/.ssh/config`: tony@167.99.207.145 with the passphrase-less `orlov-claude` key). Verify at session start with `ssh orlov "docker compose -f ~/aa-docker/docker-compose.yml ps"`.
**Division of labour (owner's rule, 2026-10-04):** for any runbook step the local session can execute (server commands, git, file edits), a cloud session does **not** hand the owner copy-paste commands. It writes one **prompt for the local session** instead: a single fenced block the owner pastes into the local session's chat, with context (what/why, runbook + section), the exact steps, verification, and the safety rules below. The owner only does what needs a human: browser clicks, Discord, EVE client, SSO logins.
Rules: read-only commands freely; any state change (config edits, restarts, `up -d`, migrations, backups) is announced in chat first with the reason, run one at a time, result shown. Never `rm -rf`, never touch `mysql-data/`, `authorized_keys`, `ufw`, or run `do-release-upgrade`. Backup (`~/bin/aa-backup.sh`) before migrations or package changes. Never print `.env` contents.

## Session handoff
The cloud session and the local session share one notebook: **`docs/handoff.md`** (owner's rule, 2026-10-04). It replaces the owner carrying summaries between chats.
- **Before resuming work with the owner:** `git pull`, then read the top entry of `docs/handoff.md`. Don't ask the owner to recap what is written there.
- **Before the owner switches sessions** (a chunk of work is finished, or the owner says they are moving to the other session): add a new entry at the top, commit, push. Entry = date, which session wrote it, runbook + section, what was done, findings/corrections, what the owner still has to do by hand, and what is next for the other session.
- A prompt for the other session (see "Division of labour" under Server access) goes in that entry's "Next" section instead of in chat. **Whenever the local session can do the next step, the cloud session writes the handoff entry, pushes, and replies with only the trigger phrase for the owner to type into the local session: "pull the latest and pick up the handoff"** (owner's rule, 2026-10-04). Nothing else is needed in chat; the entry carries the context. The rules under Server access still apply to whatever the entry asks for: state changes are announced first, one at a time.
- **Owner's command "update on progress"** (owner's rule, 2026-10-05; applies to every session — cloud, PC, laptop): `git pull`, read what came in (commit log, the top entry of `docs/handoff.md`, changed runbooks and `deploy/` files) so you know what the owner did in other sessions. Then reply with a short confirmation only: that updates were found (or that there were none) and that you are up to date, plus the open step in one line. No lengthy recap, no work on the server.
- Newest entry on top; keep the last five, older ones live in git history. No secrets, and no fenced blocks in the file.

## Secrets
Never commit `.env`, tokens, client secrets or passwords. They live on the server (`~/aa-docker/.env`) and in the owner's Bitwarden. Templates with placeholders go in `deploy/`.

## Conventions
- Markdown docs; runbooks numbered in execution order.
- Commit after each completed runbook/doc change; push to the working branch.
- Don't create pull requests unless asked.
