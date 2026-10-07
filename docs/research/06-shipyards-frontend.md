# Shipyards front door: `shipyards.orlovfamily.space` — plan

*Research 2026-10-07 (laptop session). Decisions by the owner the same day. Builds on `05-industry-dashboard.md` (the Shipyard plugin, runbook 13).*

## 1. What the owner wants

1. A member opens **shipyards.orlovfamily.space** and sees the Shipyard, not auth.
2. The only way in is **EVE SSO**. Everything the app needs comes from ESI, so a member cannot use it with wrong data (no hand-typed skills or taxes).
3. The characters a member already has on auth are **right there**: pick one, its data is used.

Owner's decisions:
- **Who:** every account with the `Family Member` or `Family Friend` state.
- **Scopes:** pull in **everything** — the same 33 scopes Member Audit asks for (assets, blueprints, industry jobs, skills, standings, wallet, mining, …). Members have been allowed to stop at the basic auth login so far; the moment they want our tools they grant the full set, once per character.
- **Where:** the existing server. Checked 2026-10-07: 1.8 GB of 3.9 GB memory free, CPU load 0.2 on 2 cores, 68 GB disk free. The front door adds no process (same Django app under a second hostname); the extra ESI reads per login are negligible.

## 2. Design: one application, two front doors

The Shipyard stays an Alliance Auth app (same database, same users, same ESI tokens). What changes:

| Piece | How |
|---|---|
| **Hostname** | DNS `A` record `shipyards.orlovfamily.space` → 167.99.207.145 at Porkbun (the domain's DNS provider). In Nginx Proxy Manager a second proxy host with its own Let's Encrypt certificate, forwarding to the same `nginx` container as auth. |
| **Django under two names** | `CSRF_TRUSTED_ORIGINS` gets the new origin; `SESSION_COOKIE_DOMAIN` and `CSRF_COOKIE_DOMAIN` become `.orlovfamily.space`, so one login is valid on both hostnames. (`ALLOWED_HOSTS` is already `*`.) |
| **Routing** | A small middleware in the plugin: on the shipyards host every path outside `/shipyard/`, `/sso/`, `/static/`, `/account/` goes to the dashboard; on the auth host every `/shipyard/…` path redirects to the shipyards host. Result: the Shipyard lives at the new address only, and auth's menu entry is a link to it. |
| **Login** | Not logged in on the shipyards host → redirect to auth's SSO login with `next=/shipyard/go/`. Auth only accepts a relative `next` (checked in `sso_login`), so `/shipyard/go/` is a one-line bounce back to `https://shipyards.orlovfamily.space/`. A character that is not on auth yet goes through auth's normal registration first, so every user is an auth user. |
| **Access** | The existing permission `shipyard.basic_access`, granted to the states `Family Member` and `Family Friend` (so it follows membership automatically). Anyone else sees a short "not for you" page with a link to auth. |
| **Look** | A standalone Bootstrap 5 page: top bar with "Orlov Shipyard", the three sections, the character picker, the member's name, links to auth and logout. Same CSS and JS bundles auth ships (Bootstrap, Font Awesome, DataTables), no auth sidebar. |
| **Character picker** | Lists the account's characters (auth's `CharacterOwnership`). Choosing one requires a token with the **full scope set**: a character already registered in Member Audit has it (no SSO prompt); any other character gets one SSO prompt for all 33 scopes. That token is then also what Member Audit needs, so the character is registered there in the same step. |
| **Data, always from ESI** | Skills and standings of the chosen character are read on first use and refreshed when older than a day, through the stored token, with no click. The hand-typed skill levels and the tax overrides are removed. Facility and market remain choices (they are not character data). |
| **Later (phase 2)** | With blueprints and industry jobs in scope: show the member's own blueprints with their ME/TE and use them in the calculation, list running jobs, and materials on hand from assets. |

Why not a separate application: it would need its own EVE developer application, its own user table and a bridge to auth to learn which characters belong to whom, and it would copy data auth already holds. Every later feature would be built twice.

## 3. Phases and who does what

| Phase | What | Who |
|---|---|---|
| 0 | DNS record at Porkbun; proxy host + certificate in Nginx Proxy Manager (`ssh -L 8181:127.0.0.1:81`, see Day 1). Can be done while phase 1 is built. | owner (runbook 14 A) |
| 1 | Plugin 0.2.0: middleware, bounce view, standalone layout, character picker with full scopes, automatic ESI refresh, manual entries removed; settings block additions; release per runbook 13 C; permission to the two states. | local session (runbook 14 B) |
| 2 | Blueprints, industry jobs and assets in the dashboard. | later, after the owner has used phase 1 |

## 4. Risks and limits

- **Changing the cookie domain** logs nobody out (the old host-only cookie stays valid on auth); new logins get the shared cookie. If a browser ever holds both cookies and misbehaves, logging out and in once fixes it.
- **Session mixing:** the same login is used on both hosts by design. Logging out on one logs out of both.
- **The SSO callback stays on auth** (`ESI_SSO_CALLBACK_URL` is unchanged; nothing to change in the EVE developer application).
- **Scope refusal:** a member who declines scopes in the SSO window gets no token and the picker says so; nothing half-loaded is stored.
- **Grafana and the proxy** are unaffected; only auth's `nginx` upstream gets a second server name.
