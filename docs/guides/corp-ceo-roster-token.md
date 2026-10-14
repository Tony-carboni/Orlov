# For corp CEOs: let auth see your corp's roster

*5 minutes, once per corp. Everything happens on https://auth.orlovfamily.space in your browser. If anything here does not match what you see, tell the alliance executor.*

## Why

Auth only knows the pilots who registered themselves. It cannot see the rest of your corp, so nobody can tell who still has to auth. One login with a character of yours fixes that: EVE lets any member read their own corp's member list, and auth keeps that list fresh every hour. Nothing else is read from your corp: no wallet, no assets, no mail.

## Before you start

- You have an auth account with the EVE SSO button (member guide steps 1 to 3). If not, do those first.
- The executor has put you in the **Corp Director** group. You can tell by the `Corp Director` role on your Discord name. Without it the page in step 2 says you have no permission.

## Step 1 — Register the character in Member Audit

1. Log in at **https://auth.orlovfamily.space** with the EVE SSO button.
2. Left menu → **Member Audit** → **Add character** (on some screens the button reads **Register**).
3. EVE's login window opens. Log in with a character **that is in your corp**, ideally your main. The window lists the permissions auth asks for (33 of them, all read-only, including "read corporation membership"). Click **Authorize**.
4. Back in Member Audit the character shows as a card. The first data pull takes a few minutes; you do not have to wait for it.

Already registered that character in Member Audit? Skip to step 2.

## Step 2 — Hand auth the roster token

1. Open **https://auth.orlovfamily.space/corpstats/add/**.
2. Auth shows the characters of yours that can read a corp's roster. Click the one that is in your corp. No EVE login appears, the token from step 1 is reused.
3. You land on **Corporation Stats** with your corp selected: member count, how many have registered, and two lists, *registered* and *unregistered*.

✅ Done when the member count on that page matches the corp window in game. Tell the executor you are done.

## Afterwards: using the page

- Left menu → **Corporation Stats** → your corp. **Unregistered** is the list of pilots who have not authed yet. Send them the member guide; it is pinned in `#how-to-auth`.
- Someone registered an alt but not their main? The alt appears under *registered*, the main stays under *unregistered* until they add it to the same auth account (dashboard → **Add Character**).
- Click **Update** on the page to refresh now instead of waiting for the hour.
- A director of yours should see the same page once the executor has added them to the Corp Director group; they can also do step 2 with a character of their own.

## If something is off

- **"You do not have permission" on the add page** → you are not in the Corp Director group yet. Ask the executor.
- **The add page lists no character of my corp** → the character in your corp is not registered (step 1), or it is on another auth account. Add it to yours: dashboard → **Add Character**, then step 1.
- **Member count differs from the game** → EVE's answer is cached for up to an hour; click **Update** later or wait for the next refresh.
- **A pilot says they authed but is listed as unregistered** → they authed with another character. The one in your corp must be added to their account (dashboard → **Add Character**).
- **Your token character leaves the corp** → the page shows an error at the next refresh. Repeat step 2 with another character of yours in the corp; it replaces the old token.
