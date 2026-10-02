# Orlov — project notes for Claude

## What this repo is
Documentation and deployment config for **The Orlov Family** (EVE Online alliance, ticker ORLOV; executor corp Orlov Arms International, OARMI) member-management platform, built on **Alliance Auth** (Docker) with Discord role sync.

- `docs/research/` — why Alliance Auth was chosen over SeAT/Neucore, and the phased plan
- `docs/design/membership.md` — states, groups → Discord roles, policies (source of truth for AA config)
- `docs/runbooks/` — step-by-step, beginner-level runbooks (`00` Day 0 prep, `01` deploy, `02` membership + Discord, `03` nicknames + Member Audit, `04` operations)
- `docs/guides/` — documents for other people: the member guide (for `#how-to-auth`) and the corp CEO onboarding checklist
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

## Secrets
Never commit `.env`, tokens, client secrets or passwords. They live on the server (`~/aa-docker/.env`) and in the owner's Bitwarden. Templates with placeholders go in `deploy/`.

## Conventions
- Markdown docs; runbooks numbered in execution order.
- Commit after each completed runbook/doc change; push to the working branch.
- Don't create pull requests unless asked.
