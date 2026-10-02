# Joining The Orlov Family — setting up your access

*Pinned in `#how-to-auth`. About 10 minutes. You only do this once; after that everything is automatic.*

**What this is:** we use a website ("auth") where you prove which EVE characters are yours. It then gives you the right Discord roles and keeps them up to date by itself. You never type a password into it — you log in through EVE's own login page, the same one the game launcher uses.

**What you need:** your EVE account login, a Discord account, and a browser. Do this on a PC/laptop, not a phone — the EVE login page is fiddly on mobile.

---

## Step 1 — Log in to auth with your main character

1. Open **https://auth.orlovfamily.space** in your browser.
2. Click the big **Log in with EVE Online** button.
3. You land on EVE's login page (`login.eveonline.com` — check the address bar). Enter your EVE account email and password. If you have two-factor on your EVE account, it'll ask for the code.
4. A list of characters on that account appears. Click your **main** — the character you play most.
5. A page asks you to *Authorize* the app "The Orlov Family Auth" to read **public data**. Click **Authorize**.
6. First time only: a **Registration** page asks for an email address. Type one and click **Register** — no confirmation mail is sent, it's just kept on file so leadership can reach you if needed.
7. You're on the **Dashboard**. Your main's portrait is there with corp and alliance.

✅ Done when the dashboard shows your main. If it shows *State: Guest*, your character isn't in an alliance corp yet — tell your CEO.

## Step 2 — Add your other characters (recommended)

Each alt is added the same way, one at a time:

1. Dashboard → **Add Character** (dark button above the character list).
2. EVE's login page opens again. **If it goes straight through without asking who you are**, it's remembering your last login — use the *Not you? / Log out* link on that page, then log in with the account that holds the alt.
3. Pick the alt, click **Authorize**.
4. Repeat for every character you want linked. Alts on the same EVE account or on different accounts both work.

Check: the dashboard's character list shows all of them. If the wrong one is marked as your main, use **Change Main**.

Why: leadership can see who an alt belongs to, so you don't get kicked out of channels for "being a random pilot".

## Step 3 — Link Discord

1. Make sure you're logged into Discord in this browser (open discord.com in another tab; if it shows your servers, you're good).
2. In auth, left menu → **Services**.
3. On the Discord card, click the orange **✓** button.
4. Discord asks: *"The Orlov Family auth wants to access your account — username, join servers for you"*. Click **Authorise**.
5. You're sent back to auth; the Discord card now shows **Enabled** and your Discord name.

Now look at Discord: you've been added to *The Orlov Family* server (if you weren't already), you have the **Family Member** role plus your corp's role (e.g. `corp_OARMI`), and your nickname has become `[CORP] Character Name`. The alliance channels are visible.

✅ Done when you can see `#general`. If you only see `#how-to-auth`, wait one minute and check again; still nothing → ask in `#how-to-auth`.

## Step 4 — Register in Member Audit (main required, alts welcome)

This is the step that grants more detailed access to your character data. Leadership uses it for one thing: knowing who is still active (last login) and keeping the roster honest. It cannot act on your character — no one can fly it, move items, or spend ISK with it.

1. In auth, left menu → **Member Audit**.
2. Click **Register** (or **Add character**).
3. EVE's login page opens with a *long* list of permissions (assets, skills, wallet, location, …). That list is what "detailed access" means. Pick the character, click **Authorize**.
4. Back in Member Audit, the character appears as a card. The first data pull takes a few minutes.
5. Do it at least for your **main**. Alts are optional but appreciated.

✅ Done when your main's card shows and, after a few minutes, opening it shows a *Last login* date.

---

## That's it

From now on everything is automatic: change corp → roles update within the hour; leave the alliance → roles are removed; nothing to maintain.

**Want to FC?** auth → left menu **Groups** → click **Request** next to `FC`. A director approves it; then the `FC` role and `#fc-chat` appear.

**Common hiccups**
- *"redirect_uri mismatch" or an EVE error page* — go back to https://auth.orlovfamily.space and start the step again; it's a one-off glitch on EVE's side.
- *Discord says "You need a verified email or phone number"* — your Discord account has no verified email. Discord → User Settings → My Account → verify it, then redo step 3.
- *Discord step says "Unknown error"* — you're logged into a different Discord account in the browser than in the app. Log out of Discord in the browser, log in with the right one, repeat step 3.
- *A character shows under the wrong main / you sold or transferred a character* — tell a director; it's a two-click fix on our side.

Questions: `#how-to-auth`, or tag an **Alliance Director** in `#general`.
