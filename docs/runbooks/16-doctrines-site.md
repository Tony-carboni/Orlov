# Runbook 16 — the doctrines site: doctrines.orlovfamily.space

*Prerequisite: runbook 14 (the Shipyard front door), whose mechanics this reuses. Time: 10 min for you (DNS and proxy), the rest by the local session, then writing the doctrines in the admin at your own pace.*

**Goal:** https://doctrines.orlovfamily.space shows the alliance's fleet doctrines to members only. A visitor is sent to auth's EVE login; a logged-in member whose main is in the alliance sees a landing page with the fleet philosophy and clickable tiles in four rows (Light & cheap, Bread and butter, Support, APEX); each tile opens the doctrine's page with its description, pros, cons, strategy notes and the ships, each with cost at Jita, net Platinum insurance, loss if lost, SRP level, and, on click, the fitting with a copy-to-clipboard button for the game. Anyone else gets a short "not for you" page. Nothing is public.

How it works (short): the plugin `apps/doctrines/` is the same kind of thing as the Shipyard: a second hostname on the same Django application, routed by a small middleware, one login cookie for `.orlovfamily.space`, the permission `doctrines | general | Can read the fleet doctrines` on the `Family Member` state. Content is edited in auth's admin. Prices come from Fuzzwork (Jita IV-4, hourly), insurance from EVE's own table (daily), fittings are pasted from the game's export and parsed once on save.

## Known values

| Item | Value |
|---|---|
| Address | `https://doctrines.orlovfamily.space` (the alliance domain is `.space`; the request said `.com`, taken as a slip) |
| Who may read | state `Family Member` (permission `doctrines.basic_access`); `Family Friend` and guests see "not for you" |
| Who may edit | the superuser, and anyone with `doctrines.manage_doctrines` (give it to `Alliance Director`, or to FCs by group) |
| Where to edit | https://auth.orlovfamily.space/admin/doctrines/ |
| Settings | `DOCTRINES_HOST`, `DOCTRINES_MARKET_STATION_ID` (Jita IV-4), `DOCTRINES_INSURANCE_LEVEL` (Platinum) in `conf/local.py`; block "Doctrines" at the end of `deploy/conf/local.py.append` |
| Package | `orlov-doctrines` from the repo archive, `#subdirectory=apps/doctrines`, pinned to the same commit as the Shipyard in `conf/requirements.txt` |
| Tasks | `doctrines_refresh_prices` hourly at :35, `doctrines_refresh_insurance` daily 05:40 |
| Seed | `manage.py doctrines_seed` (the four categories, four SRP levels, a placeholder landing text) |

---

## A. DNS and proxy (you, 10 min)

Exactly as runbook 14 A, with the new name:

1. **Porkbun → DNS records for `orlovfamily.space`** → add: type `A`, host `doctrines`, answer `167.99.207.145`, TTL default. ✅ `nslookup doctrines.orlovfamily.space` on the PC answers with the server's IP.
2. **Nginx Proxy Manager** (tunnel from the PC with `ssh -L 8181:127.0.0.1:81 orlov`, the alias, not the plain `tony@` address; then http://localhost:8181): **Hosts → Proxy Hosts → Add Proxy Host**. Domain `doctrines.orlovfamily.space`; Scheme, Forward Hostname and Forward Port **exactly as the `shipyards.orlovfamily.space` host** (open it and copy); Block Common Exploits on; Websockets on. SSL tab: Request a new certificate, Force SSL, HTTP/2, agree. **Save**.
3. ✅ Done when https://doctrines.orlovfamily.space shows auth's login page (the host is still switched off at this point, so you see plain auth; that is expected).

## B. Release with the host switched off (local session)

Same procedure as runbook 13 C for the Shipyard, plus the app's first install:

1. Backup with `~/bin/aa-backup.sh`; copies of `conf/requirements.txt` and `conf/local.py` to `~/backups`.
2. `conf/requirements.txt`: add the `orlov-doctrines` line pinned to the commit; `conf/local.py`: append the Doctrines block from `deploy/conf/local.py.append` with `DOCTRINES_HOST = ""`.
3. Build; throwaway container: `check`, `migrate doctrines`, `doctrines_seed`, `collectstatic`; `up -d`; `restart nginx`.
4. Permissions: `doctrines | general | Can read the fleet doctrines` on the state **Family Member**; `Can edit doctrines, ships and fittings` on the group **Alliance Director**.
5. First data: `manage.py shell` → `doctrines.tasks.refresh_insurance()` once (the hourly price task has nothing to price until a fitting exists).

✅ Done when https://auth.orlovfamily.space/doctrines/ shows the landing page with the placeholder text and the admin lists Doctrines.

*Done 2026-10-17 09:02–09:20 UTC by the desktop session: backup `aa-db-2026-10-17-0902.sql.gz`, `requirements.txt.pre-doctrines` and `local.py.pre-doctrines` in `~/backups`, `orlov-doctrines` pinned to commit `6495158` (the Shipyard pin untouched at `695b655`), the Doctrines block appended to `conf/local.py` with `DOCTRINES_HOST = ""`, build, `check`, migration 0001, `doctrines_seed` (4 categories, 4 SRP levels, placeholder text), collectstatic, `up -d`, nginx; permissions set (read on the state `Family Member`, read and manage on the group `Alliance Director`); insurance table read once (570 hulls at Platinum). Checks on the live stack: anonymous → login, the owner 200 with the landing text and the menu entry, a Family Friend sent away, the admin 200, both beat entries present, 0 gunicorn errors. An **inactive sample doctrine "Example: Rail Harpies"** with a real Harpy fitting proved the whole path (14 types resolved through EVE, cost 37.5 M, net insurance 3.8 M, loss 33.7 M); it is hidden from members: edit it into a real doctrine or delete it in the admin. Note for shell work: in auth's `manage.py shell -c`, add permissions to a state or group by primary key (`add(perm.pk)`); the auto-imported namespace carries a second `Permission` class and `add(perm)` raises a TypeError.*

## C. Switch the host on (local session, after A)

Set `DOCTRINES_HOST = "doctrines.orlovfamily.space"` in `conf/local.py` (copy of the file first), restart gunicorn and the workers, and check from the server: a visitor on the new host → 302 `/doctrines/` → 302 auth's SSO login with `next=/doctrines/go/`; `https://auth.orlovfamily.space/doctrines/` → 302 to the new host; auth itself 200.

*Done 2026-10-17 10:30 UTC by the desktop session, right after A (the proxy host `doctrines.orlovfamily.space` → http://nginx:80 with a Let's Encrypt certificate, added by the owner through the tunnel `ssh -L 8181:127.0.0.1:81 orlov`; the plain `tony@…` form fails with "Permission denied (publickey)" because only the alias carries the key): copy `local.py.pre-doctrines-host` in `~/backups`, the setting changed, gunicorn, the workers and beat restarted. Checks: the new host → 302 `/doctrines/` → 302 `https://auth.orlovfamily.space/sso/login?next=/doctrines/go/`; auth's `/doctrines/` → 302 to the new host; auth's own login unchanged; 0 gunicorn errors. The site is live for members; D and E remain for the owner.*

## D. Write the doctrines (you, admin, at your pace)

1. **Landing text:** admin → Doctrines → *Landing page text* → the one row → write the philosophy. Plain text; a blank line starts a paragraph, a line beginning with `- ` is a bullet.
2. **Categories and SRP levels** are seeded; rename, reorder or add under *Categories* and *SRP levels* (an SRP level has a colour for its badge and a one-line description shown on hover).
3. **A doctrine:** *Doctrines → Add*: category, name, gameplay (short: Home defense, Faction warfare, Wormhole, Nullsec roam, ...), summary (the tile's line), description, strengths and weaknesses (one per line, written as `Keyword - description`, e.g. `King of the hill - Takes a point and holds it`; the keyword comes out bold), strategy notes, **SRP percent** (e.g. 50: shown as a tag on the tile and the page, taken off the loss column). Leave *tile type id* empty to picture the first ship, or put a type id to picture another hull.
4. **Its ships**, in the inline block under the doctrine: order, fit name, role (DPS, Logi, Tackle, Support, EWAR, Boosts, Scout, FC), **variant** (`T1` or `T2` when the same hull and role has a lower-skill and a full-skill fit; the page then shows the hull once and the two fits behind T1 / T2 buttons; leave blank for a single fit), SRP level, a notes line, and the **fitting pasted from the game**: fitting window → **Export** (the arrow icon) → **To clipboard** → paste. Save. The *ship type name* column fills in; a *parse error* means EVE did not know a line (a typo, or a module renamed by a patch): fix the text and save again. New items are priced on save. Give the two variants of a hull the same *order* number so they stay together.
5. Untick *is active* on a doctrine to hide it while you work on it.

✅ Done when the landing page shows the tiles and a doctrine page shows cost, insurance and the fitting on click.

*Doctrines 0.2.0 (2026-10-17, desktop session): the variant field and the T1 / T2 buttons, strengths and weaknesses as keyword plus description, released per runbook 13 C (migration 0002, collectstatic before `up -d`). The first doctrine, **AB Armor frigs** (Light & cheap, 8 hulls, 15 fits from the owner's fitting export), was loaded from the shell with the owner's strengths and weaknesses paraphrased; the owner reviews the texts in the admin.*

*Doctrines 0.2.1 (2026-10-17): the SRP percent per doctrine (migration 0003); the explanatory paragraph above the ships table is gone, the column headers carry it on hover. AB Armor frigs set to 50 %.*

*Doctrines 0.2.2 (2026-10-17): the fitting wheel in an opened fit, the `shipfit` web component (MIT, 396 KB, self-hosted; the one the owner remembered from other alliances' doctrine pages: hull render in the middle, modules around it by slot). Alternatives looked at and not taken: EVEShip.fit's React components (need React and self-hosted data files), quiescens' eve-ui (a list, jQuery, unmaintained). Item data in the component dates from 2021: a module newer than that is missing from the wheel but still listed beside it. No migration; collectstatic before `up -d` for the new file.*

*Doctrines 0.2.3 (2026-10-17): the ships table reads Cost, SRP, Net insurance, Final cost (cost minus SRP minus insurance), rounded as the Shipyard's reprocessing tab rounds (millions with three decimals, 100 k and up whole). No migration, no new static files.*

*Doctrines 0.2.4 (2026-10-17): the table is Cost (one decimal on millions) and SRP as a percentage; a ship's own *SRP percent* overrides the doctrine's (migration 0004; the two logi hulls of AB Armor frigs set to 100 %).*

## E. Check (you, browser)

1. Private window → https://doctrines.orlovfamily.space → auth's EVE login → the landing page under the new address, without auth's menu.
2. Click a tile, click a ship, press **Copy fit to clipboard**, then in game: fitting window → Import from clipboard → the fit appears.
3. Log in as a character whose main is not in the alliance (an alt account, or ask a Family Friend): the "not for you" page.
4. Auth's menu entry **Doctrines** opens the new address.

## Changing things later

| Wish | How |
|---|---|
| Prices from another station | `DOCTRINES_MARKET_STATION_ID` and `DOCTRINES_MARKET_NAME` in `conf/local.py`, restart gunicorn and the workers |
| Another insurance level | `DOCTRINES_INSURANCE_LEVEL` ("Basic" … "Platinum"), restart, then run the insurance task once |
| Let FCs edit | give `doctrines.manage_doctrines` to the `FC` group; they get an **Edit** link in the top bar |
| Friends may read too | add the read permission to the `Family Friend` state (the owner's rule today: members only) |
| Switch the host off | `DOCTRINES_HOST = ""`, restart; the pages stay reachable under auth's host |

## Troubleshooting

- **A ship shows "EVE does not know: …"** → the pasted text has a name EVE's item list does not match: a typo, an abbreviation, or a renamed module. Export again from the game and paste the whole block.
- **Cost shows a question mark** → an item has no price yet; the hourly task fills it, or a manager saves the doctrine again.
- **Insurance shows "–"** → the insurance table has not been read yet (section B5), or the hull is not insurable.
- **Copy button says "Copy blocked"** → the browser refuses the clipboard on that page; use *Open as text* and copy from there.
- **A member sees "not for you"** → their main character is not in an alliance corp; auth catches up within the hour after a corp change, or runbook 04 E.
