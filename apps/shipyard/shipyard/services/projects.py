"""Corporation projects of the executor corp, kept as snapshots for reports.

ESI's project routes (compatibility date 2025-09-30 or later, scope
`esi-corporations.read_projects.v1`, docs/research/08-corporation-projects-reports.md)
return totals, not a history. An hourly task copies every project with its details and
contributors into our tables and stores a snapshot per project and per contributor each
time something changed, so "ISK paid out per week" and "who contributed what this month"
come from differencing the snapshots (owner's request, 2026-10-14).

Token: a valid token with the projects scope for a character of the configured corp
(Catherine Frey for Orlov Arms International); the page offers the SSO button when none.
"""

import datetime as dt
import logging
from collections import defaultdict

from allianceauth.eveonline.models import EveCharacter
from django.utils import timezone
from esi.models import Token

from .. import app_settings
from ..models import CorpProject, ProjectContribution, ProjectSnapshot
from .http import polite_pause, session

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net"
COMPAT = "2026-08-18"  # compatibility date the project routes were checked against (2026-10-12)
PERIODS = ("day", "week", "month", "quarter")


def corp_id() -> int:
    return int(app_settings.SHIPYARD_PROJECTS_CORP_ID)


def scopes() -> list[str]:
    return list(app_settings.SHIPYARD_PROJECTS_SCOPES)


def token():
    ids = list(EveCharacter.objects.filter(corporation_id=corp_id()).values_list("character_id", flat=True))
    if not ids:
        return None
    return Token.objects.filter(character_id__in=ids).require_scopes(scopes()).require_valid().order_by("-created").first()


def _get(path: str, access_token: str, params=None) -> dict:
    r = session().get(ESI + path, params=params or {}, timeout=30,
                      headers={"Authorization": f"Bearer {access_token}", "X-Compatibility-Date": COMPAT, "Accept": "application/json"})
    r.raise_for_status()
    return r.json() or {}


def _paged(path: str, access_token: str, key: str, params=None, max_pages: int = 50) -> list:
    """Cursor-paged list routes: follow `cursor.after` until it runs out."""
    out, after, pages = [], None, 0
    params = dict(params or {})
    params.setdefault("limit", 100)
    while pages < max_pages:
        if after:
            params["after"] = after
        data = _get(path, access_token, params)
        out.extend(data.get(key) or [])
        after = (data.get("cursor") or {}).get("after")
        pages += 1
        if not after:
            break
        polite_pause()
    return out


def _kind(configuration) -> str:
    """The first configuration key, e.g. 'deliver_item', 'mine_material', 'manual'."""
    for item in configuration or []:
        if isinstance(item, dict) and item:
            return next(iter(item))
    return "unknown"


def _parse_dt(value):
    if not value:
        return None
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def refresh() -> dict:
    """Pull every project (state=All), details and contributors; store snapshots where something changed."""
    tok = token()
    if tok is None:
        raise RuntimeError("no token with the projects scope for a character of the corporation")
    access_token = tok.valid_access_token()
    cid = corp_id()
    now = timezone.now()
    listed = _paged(f"/corporations/{cid}/projects", access_token, "projects", {"state": "All"})
    seen, snapshots, contribs = set(), 0, 0
    for p in listed:
        pid = str(p["id"])
        seen.add(pid)
        row, _ = CorpProject.objects.get_or_create(project_id=pid, defaults={"corporation_id": cid, "name": p.get("name") or ""})
        changed = row.last_modified != _parse_dt(p.get("last_modified")) or row.state != (p.get("state") or "")
        progress = p.get("progress") or {}
        reward = p.get("reward") or {}
        row.name = p.get("name") or row.name
        row.state = p.get("state") or ""
        row.progress_current = int(progress.get("current") or 0)
        row.progress_desired = int(progress.get("desired") or 0)
        row.reward_initial = float(reward.get("initial") or 0)
        row.reward_remaining = float(reward.get("remaining") or 0)
        row.last_modified = _parse_dt(p.get("last_modified"))
        row.last_seen = now
        if changed or not row.details:
            try:
                d = _get(f"/corporations/{cid}/projects/{pid}", access_token)
                details = d.get("details") or {}
                contribution = d.get("contribution") or {}
                creator = d.get("creator") or {}
                row.kind = _kind(d.get("configuration"))
                row.details = {"configuration": d.get("configuration") or [], "contribution": contribution, "details": details}
                row.description = (details.get("description") or "")[:1000]
                row.career = details.get("career") or ""
                row.created = _parse_dt(details.get("created"))
                row.expires = _parse_dt(details.get("expires"))
                row.finished = _parse_dt(details.get("finished"))
                row.creator_id = int(creator.get("id") or 0)
                row.creator_name = creator.get("name") or ""
                row.reward_per_contribution = float(contribution.get("reward_per_contribution") or 0)
            except Exception as exc:  # noqa: BLE001
                logger.warning("project %s details failed: %s", pid, exc)
            polite_pause()
        row.save()
        if changed:
            ProjectSnapshot.objects.create(
                project=row, taken_at=now, state=row.state, progress_current=row.progress_current,
                reward_remaining=row.reward_remaining,
            )
            snapshots += 1
            try:
                people = _paged(f"/corporations/{cid}/projects/{pid}/contributors", access_token, "contributors")
            except Exception as exc:  # noqa: BLE001
                logger.warning("project %s contributors failed: %s", pid, exc)
                people = []
            for c in people:
                contributed = int(c.get("contributed") or 0)
                last = ProjectContribution.objects.filter(project=row, character_id=int(c["id"])).order_by("-taken_at").first()
                if last is None or last.contributed != contributed:
                    ProjectContribution.objects.create(
                        project=row, taken_at=now, character_id=int(c["id"]), character_name=c.get("name") or "",
                        contributed=contributed,
                    )
                    contribs += 1
            polite_pause()
    gone = CorpProject.objects.filter(corporation_id=cid).exclude(project_id__in=seen).update(missing=True)
    return {"projects": len(listed), "snapshots": snapshots, "contributions": contribs, "missing": gone}


# --- analysis --------------------------------------------------------------------------

def period_key(when: dt.datetime, period: str) -> str:
    d = when.date()
    if period == "day":
        return d.isoformat()
    if period == "week":
        monday = d - dt.timedelta(days=d.weekday())
        return f"{monday.isoformat()} (wk {monday.isocalendar()[1]})"
    if period == "month":
        return d.strftime("%Y-%m")
    if period == "quarter":
        return f"{d.year} Q{(d.month - 1) // 3 + 1}"
    return d.isoformat()


def payout_deltas(since=None) -> list[dict]:
    """ISK members earned per project between consecutive snapshots: the units delivered times the
    reward per unit. (Until 0.14.0 this was the reward pool going down, which also counted the
    refund a project pays back to the corp wallet when it is closed.)

    Returns [{project, taken_at, paid, progress}] newest first; the first snapshot of a project
    counts from zero so a project that was already running shows what it had paid.
    """
    out = []
    for project in CorpProject.objects.filter(corporation_id=corp_id()):
        if project.state == "Deleted" and not project.contributions.exists():
            continue  # deleted before anyone delivered: the pool went back to the wallet
        snaps = list(project.snapshots.order_by("taken_at"))
        prev_remaining, prev_progress = project.reward_initial, 0
        rate = project.reward_per_contribution or 0
        for s in snaps:
            done = max(0, s.progress_current - prev_progress)
            paid = done * rate
            if since is None or s.taken_at >= since:
                out.append({"project": project, "taken_at": s.taken_at, "paid": paid, "progress": done})
            prev_remaining, prev_progress = s.reward_remaining, s.progress_current
    out.sort(key=lambda r: r["taken_at"], reverse=True)
    return out


def pivot(deltas, period: str) -> dict:
    cells = defaultdict(lambda: defaultdict(float))
    units = defaultdict(lambda: defaultdict(int))
    totals = defaultdict(float)
    keys = set()
    for d in deltas:
        k = period_key(d["taken_at"], period)
        keys.add(k)
        name = d["project"].name
        cells[name][k] += d["paid"]
        units[name][k] += d["progress"]
        totals[k] += d["paid"]
    columns = sorted(keys, reverse=True)
    rows = sorted(((n, dict(v), dict(units[n]), sum(v.values())) for n, v in cells.items()), key=lambda r: -r[3])
    return {"columns": columns, "rows": rows, "totals": dict(totals)}


def contributor_deltas(since=None) -> list[dict]:
    """Contribution growth per character between consecutive contribution rows."""
    out = []
    for project in CorpProject.objects.filter(corporation_id=corp_id()):
        rows = list(project.contributions.order_by("character_id", "taken_at"))
        prev = {}
        for r in rows:
            delta = r.contributed - prev.get(r.character_id, 0)
            prev[r.character_id] = r.contributed
            if delta > 0 and (since is None or r.taken_at >= since):
                out.append({"project": project, "taken_at": r.taken_at, "character_id": r.character_id,
                            "name": r.character_name, "delta": delta,
                            "isk": delta * (project.reward_per_contribution or 0)})
    out.sort(key=lambda r: r["taken_at"], reverse=True)
    return out


def contributors(deltas, period: str) -> list[dict]:
    by = {}
    for d in deltas:
        row = by.setdefault(d["character_id"], {"id": d["character_id"], "name": d["name"], "units": 0, "isk": 0.0,
                                                "projects": defaultdict(int), "periods": defaultdict(float), "last": d["taken_at"]})
        row["units"] += d["delta"]
        row["isk"] += d["isk"]
        row["projects"][d["project"].name] += d["delta"]
        row["periods"][period_key(d["taken_at"], period)] += d["isk"]
        row["last"] = max(row["last"], d["taken_at"])
    out = sorted(by.values(), key=lambda r: -r["isk"])
    for r in out:
        r["projects"] = sorted(r["projects"].items(), key=lambda kv: -kv[1])
        r["periods"] = dict(r["periods"])
    return out
