# Runbook 15 — Alliance news at `alliance.orlovfamily.space`

**Goal:** a public web page where the owner publishes "State of the Union" style reports. The in-game mail or bulletin carries the summary and a link; the full read lives at https://alliance.orlovfamily.space. Written 2026-10-14.

**How it works.** The posts are Markdown files in this repo (`site/alliance/posts/`). A small script (`site/alliance/build.py`) turns them into plain HTML pages with the alliance's dark theme. On the server a tiny nginx container (`alliance_site`) serves those pages from `~/aa-docker/alliance-site/`, and Nginx Proxy Manager forwards `alliance.orlovfamily.space` to it with a Let's Encrypt certificate, exactly like the Shipyard front door (runbook 14). No login, no database, nothing of auth touched: anyone with the link can read it, which is what an in-game link needs (EVE opens links in the normal browser).

**Division of labour.** You do the DNS record and the proxy host (browser clicks). The local session does everything else, including publishing each new post.

**Machines.** `PS C:\` = your PC. Server steps are run by the local session through `ssh orlov`.

## A. DNS (you, 2 min)

1. **Porkbun → DNS records for `orlovfamily.space`** → add: type `A`, host `alliance`, answer `167.99.207.145`, TTL default.
2. ✅ Done when this answers with the server's IP (can take a few minutes):

```
nslookup alliance.orlovfamily.space
```

## B. The site and its container (local session, done 2026-10-14)

Steps the local session takes, each announced first:

1. Build the pages on the PC: from the repo root, `python site/alliance/build.py` writes `site/alliance/dist/` (index page, one page per post, the stylesheet, a 404 page, and `posts.json`: the list of posts the Shipyard's Finance tab reads to open a new reporting period at every State of the Alliance post, runbook 13 release 0.20.0).
2. On the server, create `~/aa-docker/alliance-site/` and copy the built pages into it.
3. Append the `alliance_site` service (`deploy/docker-compose.alliance-site.append`) to `~/aa-docker/docker-compose.yml`, then `docker compose up -d alliance_site`.
4. ✅ Done when, from inside the proxy container, `curl -s http://alliance_site/ | head -3` returns the page's first lines, and `docker compose ps` shows `aa-docker-alliance_site-1` as Up.

## C. Proxy host and certificate (you, 5 min)

1. **Nginx Proxy Manager** (open the tunnel as on Day 1, then http://localhost:8181): **Hosts → Proxy Hosts → Add Proxy Host**.
   - *Details:* Domain Names `alliance.orlovfamily.space`; Scheme `http`; Forward Hostname `alliance_site`; Forward Port `80`; Block Common Exploits on.
   - *SSL:* Request a new SSL Certificate, Force SSL on, HTTP/2 on, agree to the Let's Encrypt terms.
   - **Save**.
2. ✅ Done when https://alliance.orlovfamily.space shows "Alliance news" with the draft post and the padlock in the address bar.

## D. Publishing a post (every time)

1. **You write the post** as a Markdown file in `site/alliance/posts/`, named `YYYY-MM-DD-short-title.md`. The file starts with a header block, one item per line, then a blank line, then the text:
   - `title:` the headline
   - `date:` the date shown
   - `author:` who signs it (optional)
   - `summary:` one paragraph for the front page (optional)
   Headings with `##`, lists with `-`, bold with `**`, links as `[text](https://…)`. The first file, `2026-10-14-state-of-the-union-october-2026.md`, is a draft template to overwrite. Files whose name starts with `_` are ignored (drafts you are not ready to show).
2. Either commit and push the file yourself, or paste the text into the local session's chat and ask it to create the file.
3. **Tell the local session:** "publish the alliance news". It builds, copies `dist/` to the server folder, and checks the page. Nothing restarts; nginx serves the new files at once.
4. ✅ Done when https://alliance.orlovfamily.space lists the post and the post's own page opens. The link for the in-game summary is `https://alliance.orlovfamily.space/<file name without .md>.html`, for example `https://alliance.orlovfamily.space/2026-10-14-state-of-the-union-october-2026.html`.

## E. Later, if wanted

- **Members only.** A public page is the simplest thing that works with an in-game link. If a report must stay inside the alliance, the alternative is a small Alliance Auth page behind the SSO login (like the Shipyard), reachable at the same address through the front-door trick of runbook 14; readers then log in with their EVE character. Ask when needed; it is about one Shipyard-sized release.
- **Images.** Put them in `site/alliance/posts/images/` and reference them as `/images/name.png`; the build copies the folder when it exists (to be added the first time it is used).

## Troubleshooting

| Symptom | Fix |
|---|---|
| NPM says the certificate failed | DNS not propagated yet; wait and retry the SSL tab, or check `nslookup` first. |
| 502 from the proxy | The container is down: `docker compose ps alliance_site`, then `docker compose up -d alliance_site`. |
| The page shows but not the new post | The build was not copied; ask the local session to publish again, then hard-refresh (Ctrl+F5). |
| A post does not appear at all | Its file name starts with `_`, or the header block has no `title:` line (the build stops and says which file). |
