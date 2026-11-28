"""The Mail tab: a member's EVE mail, read outside the game (owner, 2026-11-28).

Read-only, and private by construction:
- only the characters on the member's own auth account, through that member's own tokens
  (scope `esi-mail.read_mail.v1`, part of the full set every Shipyard character grants);
- nobody else sees it: there is no corp or alliance view, no manager view, and the cache keys
  carry the member's user id;
- nothing is written to the database. Headers are read from ESI when the page opens and kept
  in the cache for two minutes, a mail's body when it is opened and kept for ten.
Opening a mail here does not mark it read in the game (that needs the organize scope, which
this page does not use), so the unread marks are the game's own.

ESI gives 50 headers per call, newest first; `pages` calls per character (the "Load older"
button asks for one more). A mail's body is EVE's own markup (font, br, showinfo links):
`clean_body` turns it into safe HTML, keeping line breaks and web links only.
"""

import datetime as dt
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html.parser import HTMLParser

from allianceauth.authentication.models import CharacterOwnership
from django.core.cache import cache
from esi.models import Token

from .. import app_settings
from . import esi
from .http import session

logger = logging.getLogger(__name__)

MAIL_SCOPE = "esi-mail.read_mail.v1"
PER_PAGE = 50  # ESI's fixed page size for mail headers
MAX_PAGES = 6
LABEL_INBOX, LABEL_SENT, LABEL_CORP, LABEL_ALLIANCE = 1, 2, 4, 8
KINDS = ["inbox", "corp", "alliance", "list", "sent"]
KIND_LABELS = {"inbox": "Inbox", "corp": "Corp", "alliance": "Alliance", "list": "Mailing lists", "sent": "Sent"}
NAME_KEY = "shipyard:name:%s"
NAME_SECONDS = 30 * 86400


# --- who may read what ---------------------------------------------------------------------

def token_for(user, character_id: int):
    """This member's own valid token with the mail scope for one of their characters, or None."""
    return (
        Token.objects.filter(user=user, character_id=int(character_id))
        .require_scopes([MAIL_SCOPE])
        .require_valid()
        .order_by("-created")
        .first()
    )


def owns(user, character_id: int) -> bool:
    return CharacterOwnership.objects.filter(user=user, character__character_id=int(character_id)).exists()


def characters_of(user) -> list:
    """[(character_id, character_name)] on the member's auth account, by name."""
    return list(
        user.character_ownerships.select_related("character")
        .order_by("character__character_name")
        .values_list("character__character_id", "character__character_name")
    )


# --- ESI (plain HTTP, safe to run in threads) ----------------------------------------------------

def _fetch_character(character_id: int, access_token: str, pages: int) -> dict:
    """Headers (newest first, up to pages × 50), label names with the unread total, mailing-list names."""
    headers, last = [], None
    for _ in range(max(1, pages)):
        params = {"last_mail_id": last} if last else None
        chunk = esi._authed(f"/characters/{int(character_id)}/mail/", access_token, params).json() or []
        headers.extend(chunk)
        if len(chunk) < PER_PAGE:
            break
        last = min(int(h["mail_id"]) for h in chunk)
    labels, unread, lists = {}, 0, {}
    try:
        data = esi._authed(f"/characters/{int(character_id)}/mail/labels/", access_token).json() or {}
        labels = {int(x["label_id"]): x.get("name") or "" for x in data.get("labels") or []}
        unread = int(data.get("total_unread_count") or 0)
    except Exception as exc:  # noqa: BLE001
        logger.info("mail labels of %s not read: %s", character_id, exc)
    try:
        for x in esi._authed(f"/characters/{int(character_id)}/mail/lists/", access_token).json() or []:
            lists[int(x["mailing_list_id"])] = x.get("name") or ""
    except Exception as exc:  # noqa: BLE001
        logger.info("mailing lists of %s not read: %s", character_id, exc)
    return {"headers": headers, "labels": labels, "unread": unread, "lists": lists}


def _fetch_body(character_id: int, mail_id: int, access_token: str) -> dict:
    return esi._authed(f"/characters/{int(character_id)}/mail/{int(mail_id)}/", access_token).json() or {}


def _post_names(ids: list) -> list:
    r = session().post(f"{esi.ESI}/universe/names/", params={"datasource": "tranquility"}, json=ids, timeout=30)
    r.raise_for_status()
    return r.json() or []


def resolve_names(ids, post=None) -> dict:
    """{id: name} for characters, corporations and alliances; cached for a month.

    ESI answers 404 for the whole request when one id is not a name it knows (a mailing list,
    a deleted character), so a failing chunk is split in two until the bad id stands alone.
    """
    post = post or _post_names
    ids = sorted({int(i) for i in ids if i})
    found = cache.get_many([NAME_KEY % i for i in ids]) if ids else {}
    out = {i: found[NAME_KEY % i] for i in ids if NAME_KEY % i in found}
    todo = [i for i in ids if i not in out]

    def fetch(chunk):
        if not chunk:
            return
        try:
            for row in post(chunk):
                out[int(row["id"])] = row.get("name") or ""
        except Exception:  # noqa: BLE001
            if len(chunk) > 1:
                half = len(chunk) // 2
                fetch(chunk[:half])
                fetch(chunk[half:])

    for start in range(0, len(todo), 500):
        fetch(todo[start:start + 500])
    fresh = {NAME_KEY % i: out[i] for i in todo if i in out}
    if fresh:
        cache.set_many(fresh, NAME_SECONDS)
    return out


# --- the list ------------------------------------------------------------------------------

@dataclass
class MailRow:
    character_id: int
    character_name: str
    mail_id: int
    subject: str
    from_id: int
    from_name: str
    timestamp: dt.datetime | None
    is_read: bool
    kind: str
    folders: list = field(default_factory=list)


def _parse(ts):
    try:
        return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")) if ts else None
    except ValueError:
        return None


def kind_of(header: dict) -> str:
    """One of KINDS for a header: sent beats everything, then corp, alliance, a mailing list, else inbox."""
    labels = {int(x) for x in header.get("labels") or []}
    if LABEL_SENT in labels:
        return "sent"
    if LABEL_CORP in labels:
        return "corp"
    if LABEL_ALLIANCE in labels:
        return "alliance"
    if any(r.get("recipient_type") == "mailing_list" for r in header.get("recipients") or []):
        return "list"
    return "inbox"


def folders_of(header: dict, labels: dict, lists: dict) -> list:
    """What to show in the Folder column: the mailing list's name, and the member's own labels."""
    out = []
    for r in header.get("recipients") or []:
        if r.get("recipient_type") == "mailing_list":
            out.append(lists.get(int(r.get("recipient_id") or 0)) or "Mailing list")
    for label_id in header.get("labels") or []:
        if int(label_id) > LABEL_ALLIANCE and labels.get(int(label_id)):
            out.append(labels[int(label_id)])
    return out


def _cache_key(user, character_id: int, pages: int) -> str:
    return f"shipyard:mail:{user.pk}:{int(character_id)}:{int(pages)}"


def inbox(user, pages: int = 1, force: bool = False) -> dict:
    """Every mail header of the member's characters, newest first, with what the page shows around it."""
    pages = max(1, min(MAX_PAGES, int(pages or 1)))
    boxes, jobs = [], []
    for character_id, name in characters_of(user):
        box = {"character_id": character_id, "name": name, "connected": False, "unread": 0, "count": 0, "error": "", "data": None}
        boxes.append(box)
        token = token_for(user, character_id)
        if token is None:
            continue
        box["connected"] = True
        data = None if force else cache.get(_cache_key(user, character_id, pages))
        if data is not None:
            box["data"] = data
            continue
        try:
            jobs.append((box, token.valid_access_token()))
        except Exception as exc:  # noqa: BLE001
            logger.warning("mail token of %s unusable: %s", name, exc)
            box["error"] = "EVE did not accept this character's login; log it in again under My settings."

    def run(job):
        box, access_token = job
        try:
            return box, _fetch_character(box["character_id"], access_token, pages), ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("mail of %s not read: %s", box["name"], exc)
            return box, None, "EVE did not answer for this character; try Refresh in a minute."

    if len(jobs) == 1:
        results = [run(jobs[0])]
    elif jobs:
        with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as pool:
            results = list(pool.map(run, jobs))
    else:
        results = []
    for box, data, error in results:
        box["error"] = error
        if data is not None:
            box["data"] = data
            cache.set(_cache_key(user, box["character_id"], pages), data, app_settings.SHIPYARD_MAIL_CACHE_SECONDS)

    names = resolve_names(h.get("from") for box in boxes if box["data"] for h in box["data"]["headers"])
    rows, more = [], False
    for box in boxes:
        data = box["data"]
        if not data:
            continue
        box["unread"] = data["unread"]
        box["count"] = len(data["headers"])
        more = more or len(data["headers"]) >= pages * PER_PAGE
        for h in data["headers"]:
            sender = int(h.get("from") or 0)
            rows.append(MailRow(
                character_id=box["character_id"], character_name=box["name"], mail_id=int(h["mail_id"]),
                subject=h.get("subject") or "(no subject)", from_id=sender,
                from_name=names.get(sender) or data["lists"].get(sender) or (f"#{sender}" if sender else "unknown"),
                timestamp=_parse(h.get("timestamp")), is_read=bool(h.get("is_read")), kind=kind_of(h),
                folders=folders_of(h, data["labels"], data["lists"]),
            ))
    rows.sort(key=lambda r: (r.timestamp is not None, r.timestamp, r.mail_id), reverse=True)
    for box in boxes:
        box.pop("data", None)
    return {
        "rows": rows,
        "boxes": boxes,
        "connected": [b for b in boxes if b["connected"]],
        "unconnected": [b for b in boxes if not b["connected"]],
        "unread_total": sum(b["unread"] for b in boxes),
        "kinds": [(k, KIND_LABELS[k]) for k in KINDS if any(r.kind == k for r in rows)],
        "pages": pages,
        "more": more and pages < MAX_PAGES,
        "cache_seconds": int(app_settings.SHIPYARD_MAIL_CACHE_SECONDS),
    }


# --- one mail ------------------------------------------------------------------------------

class _Cleaner(HTMLParser):
    """EVE's mail markup → safe HTML: text escaped, line breaks kept, web links kept, everything else dropped."""

    BLOCK = {"p", "div", "li", "tr", "h1", "h2", "h3"}
    SKIP = {"script", "style"}
    KILL = re.compile(r"^killReport:(\d+):[0-9a-fA-F]+$")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0
        self.link_open = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
            return
        if tag == "br":
            self.out.append("\n")
        elif tag in self.BLOCK:
            self.out.append("\n")
        elif tag == "a" and not self.link_open:
            href = (dict(attrs).get("href") or "").strip()
            target = None
            if re.match(r"^https?://", href, re.I):
                target = href
            else:
                m = self.KILL.match(href)
                if m:
                    target = f"https://zkillboard.com/kill/{m.group(1)}/"
            if target:
                self.out.append(f'<a href="{html.escape(target, quote=True)}" target="_blank" rel="noopener noreferrer nofollow">')
                self.link_open = True

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "a" and self.link_open:
            self.out.append("</a>")
            self.link_open = False
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        if self.link_open:
            self.out.append("</a>")
        text = "".join(self.out).replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text).strip("\n")
        return text.replace("\n", "<br>")


def clean_body(body: str) -> str:
    parser = _Cleaner()
    try:
        parser.feed(body or "")
        parser.close()
    except Exception:  # noqa: BLE001
        return html.escape(re.sub(r"<[^>]*>", "", body or "")).replace("\n", "<br>")
    return parser.result()


def read(user, character_id: int, mail_id: int) -> dict | None:
    """One mail of one of the member's own characters, ready to show; None when it is not theirs to read."""
    if not owns(user, character_id):
        return None
    token = token_for(user, character_id)
    if token is None:
        return None
    key = f"shipyard:mailbody:{user.pk}:{int(character_id)}:{int(mail_id)}"
    data = cache.get(key)
    if data is None:
        data = _fetch_body(character_id, mail_id, token.valid_access_token())
        cache.set(key, data, app_settings.SHIPYARD_MAIL_BODY_CACHE_SECONDS)
    recipients = data.get("recipients") or []
    plain = [int(r["recipient_id"]) for r in recipients if r.get("recipient_type") != "mailing_list" and r.get("recipient_id")]
    sender = int(data.get("from") or 0)
    names = resolve_names(plain + [sender])
    to = []
    for r in recipients:
        rid = int(r.get("recipient_id") or 0)
        if r.get("recipient_type") == "mailing_list":
            to.append("Mailing list")
        else:
            to.append(names.get(rid) or f"#{rid}")
    stamp = _parse(data.get("timestamp"))
    return {
        "subject": data.get("subject") or "(no subject)",
        "from": names.get(sender) or (f"#{sender}" if sender else "unknown"),
        "to": to,
        "timestamp": stamp.strftime("%a %d %b %Y %H:%M") + " EVE" if stamp else "",
        "body_html": clean_body(data.get("body") or ""),
    }
