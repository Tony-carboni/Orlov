"""The Projects page (0.41.0, owner, 2026-11-25): what the officers who manage the corporation's
projects need at a glance.

- Every running project with how full it is, flagged when nearly full (SHIPYARD_PROJECTS_NEARLY_PCT,
  75 % and up) and when completed.
- The ores the corporation buys through its projects, each with Jita's best buy order, nothing else:
  the highsec R4 moon ores, the highsec asteroid ores (Veldspar, Scordite, Plagioclase, Omber) and
  ice, all in their compressed form, which is what the projects take. Ice is not priced from the
  market: every block counts SHIPYARD_PROJECTS_ICE_ISK (150,000 ISK), the corporation's own rate.

The projects come from the hourly read of services/projects.py; the prices from the hourly Jita
refresh (tasks.refresh_prices includes these types).
"""

import datetime as dt

from django.utils import timezone

from .. import app_settings
from ..models import CorpProject, MarketLocation, MaterialType, PriceSnapshot
from . import projectbooks, projects

# (group title, [(type id, name)]); the names are fixed here so the page needs no name cache
ORE_GROUPS = [
    ("Highsec R4 moon ores", [
        (62454, "Compressed Bitumens"), (62455, "Compressed Brimful Bitumens"), (62456, "Compressed Glistening Bitumens"),
        (62457, "Compressed Coesite"), (62458, "Compressed Brimful Coesite"), (62459, "Compressed Glistening Coesite"),
        (62460, "Compressed Sylvite"), (62461, "Compressed Brimful Sylvite"), (62466, "Compressed Glistening Sylvite"),
        (62463, "Compressed Zeolites"), (62464, "Compressed Brimful Zeolites"), (62467, "Compressed Glistening Zeolites"),
    ]),
    ("Highsec asteroid ores", [
        (62516, "Compressed Veldspar"), (62517, "Compressed Veldspar II-Grade"), (62518, "Compressed Veldspar III-Grade"),
        (62520, "Compressed Scordite"), (62521, "Compressed Scordite II-Grade"), (62522, "Compressed Scordite III-Grade"),
        (62528, "Compressed Plagioclase"), (62529, "Compressed Plagioclase II-Grade"), (62530, "Compressed Plagioclase III-Grade"),
        (62532, "Compressed Omber"), (62533, "Compressed Omber II-Grade"), (62534, "Compressed Omber III-Grade"),
    ]),
    ("Ice", [
        (28433, "Compressed Blue Ice"), (28434, "Compressed Clear Icicle"), (28438, "Compressed Glacial Mass"), (28444, "Compressed White Glaze"),
    ]),
]
ICE_GROUP = "Ice"
# other things the projects deliver, named here too so the list never shows a bare type id
OTHER_NAMES = {62524: "Compressed Pyroxeres", 62525: "Compressed Pyroxeres II-Grade", 62526: "Compressed Pyroxeres III-Grade",
               62536: "Compressed Kernite", 62537: "Compressed Kernite II-Grade", 62538: "Compressed Kernite III-Grade"}
NAMES = {**OTHER_NAMES, **{tid: name for _, items in ORE_GROUPS for tid, name in items}}


def price_type_ids() -> set:
    """The ore types the page prices from the market (not the ice, which has a fixed price)."""
    return {tid for title, items in ORE_GROUPS if title != ICE_GROUP for tid, _ in items}


def nearly_pct() -> float:
    return float(app_settings.SHIPYARD_PROJECTS_NEARLY_PCT)


def ice_isk() -> float:
    return float(app_settings.SHIPYARD_PROJECTS_ICE_ISK)


def _market():
    return MarketLocation.objects.filter(is_active=True).order_by("-is_default", "name").first()


def ore_prices() -> dict:
    """{groups: [{title, rows: [{type_id, name, buy, fixed}]}], market, fetched_at}: Jita's best buy per unit, the ice at the fixed rate."""
    market = _market()
    snaps = {p.type_id: p for p in PriceSnapshot.objects.filter(location=market, type_id__in=list(price_type_ids()))} if market else {}
    fetched = max((p.fetched_at for p in snaps.values()), default=None)
    groups = []
    for title, items in ORE_GROUPS:
        rows = []
        for tid, name in items:
            if title == ICE_GROUP:
                rows.append({"type_id": tid, "name": name, "buy": ice_isk(), "fixed": True})
            else:
                snap = snaps.get(tid)
                rows.append({"type_id": tid, "name": name, "buy": (snap.buy_max if snap else None), "fixed": False})
        groups.append({"title": title, "rows": rows})
    return {"groups": groups, "market": market, "fetched_at": fetched}


def _item_name(project, names: dict) -> str:
    tid = projectbooks.delivered_type(project)
    if tid is None:
        return project.kind.replace("_", " ") if project.kind else ""
    return NAMES.get(tid) or names.get(tid) or f"type {tid}"


def flag_of(project) -> str:
    """'done' for a completed project, 'nearly' from SHIPYARD_PROJECTS_NEARLY_PCT up, else ''."""
    if project.state == "Completed" or (project.progress_desired and project.progress_current >= project.progress_desired):
        return "done"
    if project.progress_pct >= nearly_pct():
        return "nearly"
    return ""


def project_rows(cid=None, done_days: int = 30) -> dict:
    """{running: [...], done: [...], counts: {running, nearly, done}}; a row = {project, item, pct, flag, left}.

    running: the active projects, fullest first. done: the completed ones of the last done_days days, newest first."""
    cid = cid or projects.corp_id()
    since = timezone.now() - dt.timedelta(days=done_days)
    qs = CorpProject.objects.filter(corporation_id=cid, missing=False)
    type_ids = {projectbooks.delivered_type(p) for p in qs}
    names = dict(MaterialType.objects.filter(type_id__in=[t for t in type_ids if t]).values_list("type_id", "name"))
    running, done = [], []
    for p in qs:
        flag = flag_of(p)
        row = {"project": p, "item": _item_name(p, names), "pct": min(100.0, p.progress_pct), "flag": flag,
               "left": max(0, p.progress_desired - p.progress_current)}
        if flag == "done":
            if (p.finished or p.last_modified or p.created or since) >= since:
                done.append(row)
        elif p.state == "Active":
            running.append(row)
    running.sort(key=lambda r: (-r["pct"], r["project"].name.lower()))
    done.sort(key=lambda r: (r["project"].finished or r["project"].last_modified or r["project"].created or since), reverse=True)
    return {"running": running, "done": done,
            "counts": {"running": len(running), "nearly": sum(1 for r in running if r["flag"] == "nearly"), "done": len(done)}}
