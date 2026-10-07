# Runbook 14 — the Shipyard's own front door: `shipyards.orlovfamily.space`

*Prerequisite: runbook 13 (Shipyard installed; 0.2.0 or later). Plan and reasons in `docs/research/06-shipyards-frontend.md`.*
*Time: ~20 min. You do section A (DNS and proxy) and the check in D; the local session does B and C.*

**Goal:** members open **https://shipyards.orlovfamily.space**, log in with EVE (through auth's SSO), and get the Shipyard in its own clean layout. Their auth characters are offered in a picker; choosing one grants the full ESI scope set once and from then on skills and standings are read from EVE and refreshed daily. Nothing is typed by hand.

How it works (short): it is the same Django application as auth, answering under a second hostname. A small piece of the plugin routes the two names: on the new host everything leads to the Shipyard; on auth's host the Shipyard redirects to the new one. One login works on both because the login cookie is set for `.orlovfamily.space`.

## Known values

| Item | Value |
|---|---|
| Hostname | `shipyards.orlovfamily.space` → `167.99.207.145` (same server) |
| DNS | Porkbun (the domain's name servers are `*.ns.porkbun.com`) |
| Proxy | Nginx Proxy Manager on the server, admin UI at `127.0.0.1:81` (reach it with `ssh -L 8181:127.0.0.1:81 …`, Day 1); forward to the same target as `auth.orlovfamily.space` |
| Settings | block "Shipyards front door" at the end of `deploy/conf/local.py.append`: `SHIPYARD_STANDALONE_HOST`, the middleware, cookie domains, `CSRF_TRUSTED_ORIGINS` |
| Access | permission `shipyard \| general \| Can access the Shipyard dashboard` on the **states** `Family Member` and `Family Friend` |
| Scopes a character grants | the 33 Member Audit scopes (`characters.full_scopes()`); the token also registers the character in Member Audit |
| Switch off | `SHIPYARD_STANDALONE_HOST = ""` in `conf/local.py`, restart; the Shipyard is back inside auth only |

---

## A. DNS and proxy (you, 10 min)

1. **Porkbun → DNS records for `orlovfamily.space`** → add: type `A`, host `shipyards`, answer `167.99.207.145`, TTL default. ✅ `nslookup shipyards.orlovfamily.space` on the PC answers with the server's IP (can take a few minutes).
2. **Nginx Proxy Manager** (open the tunnel as on Day 1, then http://localhost:8181): **Hosts → Proxy Hosts → Add Proxy Host**.
   - *Details:* Domain Names `shipyards.orlovfamily.space`; Scheme, Forward Hostname and Forward Port **exactly as on the existing `auth.orlovfamily.space` host** (open that one first and copy them); Block Common Exploits on; Websockets Support on.
   - *SSL:* Request a new SSL Certificate, Force SSL on, HTTP/2 on, agree to the Let's Encrypt terms.
   - **Save**.
3. ✅ Done when https://shipyards.orlovfamily.space shows auth's login page (the front door is still switched off at this point, so you see plain auth; that is expected).

## B. Release 0.2.0 with the front door switched off (local session)

*Done 2026-10-07 17:05 UTC: commit `7fe6752` pinned, backup `aa-db-2026-10-07-1701.sql.gz`, settings block appended with the host empty, build, 37 tests, `up -d`, nginx, collectstatic, permission granted to both states.*

Per runbook 13 C: pin the commit, build, checks in a throwaway container, `migrate` (none for 0.2.0), `up -d`, nginx, `collectstatic`. Then append the "Shipyards front door" settings block with **`SHIPYARD_STANDALONE_HOST = ""`** for now, and grant the access permission to the two states.

Why off first: with the host set, every Shipyard page on auth redirects to the new hostname. Until A is done that address does not exist.

✅ Done when the Shipyard still works inside auth, the settings page shows the character picker, and admin → States → Family Member / Family Friend list the Shipyard permission.

## C. Switch the front door on (local session, after A)

Set `SHIPYARD_STANDALONE_HOST = "shipyards.orlovfamily.space"` in `conf/local.py`, restart gunicorn and the workers, and check from the server that the new host answers 302 → auth's SSO login for a visitor and that auth's `/shipyard/` answers 302 → the new host.

## D. Check (you, browser)

1. Open https://shipyards.orlovfamily.space in a private window: you land on auth's EVE login, log in with one of your characters, and arrive on the Shipyard dashboard under the new address, without auth's menu.
2. **My settings** → the picker lists your auth characters. Choose one: a character already in Member Audit is used at once; any other opens EVE's login for the 33 scopes once. The dashboard header then shows "character: <name>".
3. Auth's menu entry **Shipyard** now opens the new address.
4. A member without access (not Family Member or Friend) sees "The Shipyard is for members and friends of The Orlov Family".

## E. Phase 2: My industry — jobs, blueprints and stock (Shipyard 0.3.0)

*Built 2026-10-07 on the owner's request ("a full dashboard of the ongoing jobs and assets").*

A new page **My industry** (`/shipyard/industry/`), fed from the characters that have granted full access:

| Section | What it shows | Read from EVE |
|---|---|---|
| Characters strip | every character read, with build and science slots in use / available (from Mass Production, Advanced Mass Production, Laboratory Operation, Advanced Laboratory Operation) | with the jobs |
| Jobs | running jobs and jobs ready to deliver (a finished job EVE still calls "active" counts as ready), with product, runs, where, end time and cost; delivered jobs of the last 7 days folded away | every 30 minutes |
| Blueprints | every blueprint the characters own: original or copy, ME, TE, runs, where, which character; catalog ships are marked | every 6 hours |
| Stock | build materials and catalog ships on hand, per station or structure (items in containers and ship holds roll up to the place they are in), valued at the default market's lowest sell | every 6 hours |

**Your own blueprints change the numbers.** Where a member owns a blueprint of a catalog ship, the dashboard and the ship page use its ME and TE instead of ME 0 (badge "your BPO ME10"), recalculated live through EVE Ref (cached 30 minutes, at most 25 ships per page view).

**Who sees whom** (owner's rule 2026-10-07): a member sees their own characters. The permission `shipyard | general | Can see the industry of everyone in their corporation` (on the group `Corp Director`) adds a **My corp** view; `Can see the industry of everyone in the alliance` (on `Alliance Director`) adds **Alliance**. Corp and alliance are taken from the viewer's main character; only members who granted full access appear. "Refresh now" refreshes the viewer's own characters; everyone else is refreshed by the background task `shipyard_refresh_industry` (every 30 minutes at :05 and :35; blueprints and assets are only re-read when older than 6 hours).

Structures a character cannot dock at show as "Location <id>"; EVE does not give their names to outsiders.

## Troubleshooting

- **The new address shows the proxy's "Congratulations" page or a certificate error** → the proxy host in A2 is missing or its certificate failed; check the DNS record first.
- **Redirect loop between the two hosts** → `SESSION_COOKIE_DOMAIN` is not `.orlovfamily.space` or the browser still holds an old host-only cookie; log out and in once.
- **"CSRF verification failed" on Save** → `CSRF_TRUSTED_ORIGINS` lacks `https://shipyards.orlovfamily.space` (settings block).
- **Member sees the no-access page although they are Family Member** → the permission is on the groups from runbook 13 D, not on the states; or their state is wrong (check auth's dashboard).
- **"EVE's login did not give full access"** → the member logged in with a different character or declined scopes; choose again and accept everything.
