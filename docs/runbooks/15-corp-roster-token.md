# Runbook 15 — Corp roster token: let auth see who in your corp has registered

*For corp CEOs and directors. Browser only, ~3 minutes, once per corp. The alliance executor does section C.*

**Goal:** auth can list the members of your corp and show which of them have registered on auth and which have not. Without this token auth only knows the characters that registered themselves; it cannot see the rest of your corp at all, so nobody can tell who still has to auth.

How it works: EVE lets any member of a corporation read that corporation's member list. You give auth permission to do that through one of your characters ("the token"), and auth refreshes the list every hour. Your character needs no corp role for this; a plain member works. Nothing else is read: no wallet, no assets, no mail.

## Known values

| Item | Value |
|---|---|
| Who may do it | members of the `Corp Director` group (the executor adds the CEO after the corp joins; the CEO can ask for more directors) |
| Where | https://auth.orlovfamily.space/corpstats/add/ |
| Scope asked for in the EVE login window | one scope, "read corporation membership" (`esi-corporations.read_corporation_membership.v1`) |
| Where the result shows | **Corporation Stats** in the left menu of auth → your corp |
| Refresh | every hour; also when you click **Update** on the corp's page |
| Done already | OARMI (token: Catherine Frey) |

---

## A. Add the token (CEO or director, browser)

1. Log in to **https://auth.orlovfamily.space** with the EVE SSO button, using any character that is already on your auth account.
2. Open **https://auth.orlovfamily.space/corpstats/add/**. An EVE login window opens.
3. In that window choose a character **that is in your corp** (if you have several, pick the main). The window lists the single permission "read corporation membership". Click **Authorize**.
4. You land on **Corporation Stats** with your corp selected. The page shows the member count, how many have registered, and two lists: *registered* and *unregistered*.

✅ Done when Corporation Stats shows your corp with a member count that matches the corp window in game.

If the EVE window offers no character of your corp, that character is not on your auth account yet: dashboard → **Add Character** first, then try again.

## B. Use it (CEO or director)

- **Corporation Stats** → your corp → **Unregistered**: these pilots have not authed. Send them the member guide (`docs/guides/member-guide.md`, posted in `#how-to-auth`).
- A pilot who registered an alt but not their main appears under *registered* with that alt; the main shows under *unregistered* until it is added to the same account (dashboard → Add Character).
- Click **Update** on the page to refresh now instead of waiting for the hour.

## C. Executor (once per corp)

1. Admin → **Group Management → Groups → Corp Director** → add the CEO (and any director the CEO names) under *Chosen Users* → Save. Their Discord role `Corp Director` follows within a minute. Since 2026-10-14 the group carries the permissions *Can add corp stats* and *Can view corp stats*, so nothing else is needed per person.
2. Ask the CEO to do section A. Check **Corporation Stats** → *Corporations ▾* lists the corp afterwards.

✅ Done when every alliance corp appears in *Corporations ▾* and the executor sees all of them (the `Alliance Director` group has *Can view alliance corp stats*).

## Changing things later

| Wish | How |
|---|---|
| The token character left the corp or was removed | the corp's page shows an error at the next refresh; any director adds a new token with section A, which replaces the old one |
| Another corp joins | section C, then the CEO does section A; also the steps in `docs/guides/corp-ceo-onboarding.md` |
| A director may also see members' characters in Member Audit | that is a separate permission on the `Corp Director` group (runbook 03 C2), already set |

## Troubleshooting

- **"You do not have permission" on the add page** → you are not in the `Corp Director` group yet. Ask the executor (section C1).
- **The EVE window shows no character of my corp** → add it to your auth account first (dashboard → Add Character), then open the add page again.
- **Member count in auth differs from the game** → EVE's answer is cached up to an hour; click **Update** after an hour or wait for the next refresh.
- **A pilot is listed as unregistered but says they authed** → they authed with another character; the one in your corp must be added to their account (dashboard → Add Character).
