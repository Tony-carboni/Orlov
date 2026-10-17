"""EVE's insurance table (ESI /insurance/prices/, public): premium and payout per hull at one level."""

import logging

from django.utils import timezone

from .. import app_settings
from ..models import Insurance
from . import get_json

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"


def refresh() -> dict:
    """Store the configured level (Platinum) for every hull in the table."""
    level = app_settings.DOCTRINES_INSURANCE_LEVEL
    data = get_json(f"{ESI}/insurance/prices/", params={"datasource": "tranquility"})
    now = timezone.now()
    n = 0
    for row in data:
        for lv in row.get("levels") or []:
            if lv.get("name") == level:
                Insurance.objects.update_or_create(
                    type_id=int(row["type_id"]),
                    defaults={"level": level, "cost": float(lv.get("cost") or 0), "payout": float(lv.get("payout") or 0), "updated_at": now},
                )
                n += 1
    return {"hulls": n, "level": level}


def net_map(type_ids) -> dict:
    """{type_id: (cost, payout, net)} for the given hull ids."""
    return {i.type_id: (i.cost, i.payout, i.net) for i in Insurance.objects.filter(type_id__in=list(type_ids))}
