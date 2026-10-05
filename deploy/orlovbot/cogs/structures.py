"""The structure board: one message for directors with every structure we own.

Per structure: state, power mode, fuel left, offline services and the structure profile.
Per owning corp: war eligibility and the wars known from EVE notifications.
Data comes from aa-structures (which reads EVE every 30 minutes) plus two small reads of
EVE's API of our own: war eligibility (public) and the profile number per structure
(with the structures token aa-structures already holds). docs/runbooks/10-structure-board.md
"""

import datetime as dt
import logging
import time

import requests
import yaml
from asgiref.sync import sync_to_async
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings
from django.utils import timezone

from orlovbot.board import CHECK_MINUTES, Board

logger = logging.getLogger(__name__)

BOARD_TITLE = "Structure status"
ESI = "https://esi.evetech.net/latest"
ESI_HEADERS = {"User-Agent": "orlov-auth structure board (allianceauth-discordbot cog)"}
ESI_CACHE_SECONDS = 3600  # war eligibility and profiles change rarely
FUEL_WARNING_DAYS = 7
STATE_NORMAL = 11  # aa-structures: shield vulnerable, the resting state of an Upwell structure
STRUCTURES_SCOPE = "esi-corporations.read_structures.v1"

# EVE notification types, as aa-structures stores them
WAR_START = {"WarDeclared", "DeclareWar", "WarAdopted", "WarInherited"}
WAR_END = {
    "WarInvalid",
    "WarRetracted",
    "WarRetractedByConcord",
    "WarConcordInvalidates",
    "WarEndedHqSecurityDrop",
    "AllWarSurrenderMsg",
    "CorpWarSurrenderMsg",
    "WarHQRemovedFromSpace",
}
WAR_ELIGIBILITY_LOST = "CorpNoLongerWarEligible"

_cache = {}


def _cached(key, fetch):
    """Value from the last hour, else fetch it. A failed fetch keeps the old value."""
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < ESI_CACHE_SECONDS:
        return hit[1]
    try:
        value = fetch()
    except Exception as ex:
        logger.warning("Structure board: could not read %s from EVE: %s", key[0], ex)
        return hit[1] if hit else None
    _cache[key] = (time.monotonic(), value)
    return value


def _filetime(value) -> dt.datetime:
    """EVE notifications carry times as 100 ns ticks since 1601 (Windows FILETIME)."""
    return dt.datetime(1601, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(
        microseconds=int(value) // 10
    )


def _war_eligible(corporation_id: int):
    def fetch():
        response = requests.get(
            f"{ESI}/corporations/{corporation_id}/", headers=ESI_HEADERS, timeout=20
        )
        response.raise_for_status()
        return response.json().get("war_eligible")

    return _cached(("war eligibility", corporation_id), fetch)


def _profiles(owner) -> dict:
    """Profile number per structure id. EVE's API has the number only, never the name."""
    from esi.models import Token

    corporation_id = owner.corporation.corporation_id

    def fetch():
        characters = owner.characters.filter(is_enabled=True).select_related(
            "character_ownership__character"
        )
        for owner_character in characters:
            character_id = owner_character.character_ownership.character.character_id
            token = (
                Token.objects.filter(character_id=character_id)
                .require_scopes([STRUCTURES_SCOPE])
                .require_valid()
                .first()
            )
            if not token:
                continue
            response = requests.get(
                f"{ESI}/corporations/{corporation_id}/structures/",
                headers={
                    **ESI_HEADERS,
                    "Authorization": f"Bearer {token.valid_access_token()}",
                },
                timeout=20,
            )
            response.raise_for_status()
            return {row["structure_id"]: row.get("profile_id") for row in response.json()}
        raise RuntimeError("no valid structures token")

    return _cached(("structure profiles", corporation_id), fetch) or {}


def _entity_name(entity_id) -> str:
    if not entity_id:
        return "unknown"
    try:
        from eveuniverse.models import EveEntity

        return EveEntity.objects.resolve_name(entity_id) or f"#{entity_id}"
    except Exception:
        return f"#{entity_id}"


def _wars(owner, now) -> list:
    """Wars that are declared or running, reconstructed from the owner's EVE notifications.

    A war starts with a declaration and ends with one of the WAR_END notifications or
    when the corp stops being war eligible. Without an end signal a war counts as running,
    so a missed notification errs towards showing a war that is already over.
    """
    from structures.models import Notification

    wars = {}
    notifications = Notification.objects.filter(
        owner=owner, notif_type__in=WAR_START | WAR_END | {WAR_ELIGIBILITY_LOST}
    ).order_by("timestamp")
    for notification in notifications:
        try:
            data = yaml.safe_load(notification.text) or {}
        except yaml.YAMLError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        key = (data.get("declaredByID"), data.get("againstID"))
        kind = notification.notif_type
        if kind in WAR_START:
            if data.get("timeStarted"):
                fight_from = _filetime(data["timeStarted"])
            else:
                fight_from = notification.timestamp + dt.timedelta(
                    hours=data.get("delayHours") or 24
                )
            wars[key] = {
                "by": key[0],
                "against": key[1],
                "declared": notification.timestamp,
                "fight_from": fight_from,
                "ends": None,
            }
        elif kind in WAR_END:
            if data.get("endDate"):
                ends = _filetime(data["endDate"])
            elif kind == "WarHQRemovedFromSpace":
                ends = notification.timestamp + dt.timedelta(hours=24)
            else:
                ends = notification.timestamp
            if key in wars:
                targets = [wars[key]]
            else:
                targets = [war for war in wars.values() if war["ends"] is None]
            for war in targets:
                war["ends"] = ends
        else:  # no longer war eligible: every war against the corp is over
            for war in wars.values():
                if war["ends"] is None:
                    war["ends"] = notification.timestamp

    ours = {owner.corporation.corporation_id}
    if owner.corporation.alliance:
        ours.add(owner.corporation.alliance.alliance_id)
    active = []
    for war in wars.values():
        if war["ends"] is not None and war["ends"] <= now:
            continue
        war["we_declared"] = war["by"] in ours
        war["other"] = _entity_name(war["against"] if war["we_declared"] else war["by"])
        active.append(war)
    return sorted(active, key=lambda war: war["declared"])


def collect() -> list:
    """Everything the board shows, as plain data. Runs in a thread: database and HTTP."""
    from structures.models import Owner, Structure

    now = timezone.now()
    profile_names = getattr(settings, "ORLOVBOT_STRUCTURE_PROFILES", {})
    owners = []
    for owner in (
        Owner.objects.filter(is_active=True)
        .select_related("corporation", "corporation__alliance")
        .order_by("corporation__corporation_name")
    ):
        profiles = _profiles(owner)
        structures = []
        for structure in (
            Structure.objects.filter(owner=owner)
            .select_related("eve_type", "eve_solar_system")
            .prefetch_related("services")
            .order_by("name")
        ):
            if structure.is_poco or structure.is_skyhook:
                continue
            profile_id = profiles.get(structure.id)
            structures.append(
                {
                    "name": structure.name,
                    "type": structure.eve_type.name,
                    "system": structure.eve_solar_system.name,
                    "state": structure.state,
                    "state_text": structure.get_state_display().strip(),
                    "state_timer_end": structure.state_timer_end,
                    "is_reinforced": structure.is_reinforced,
                    "is_full_power": structure.is_full_power,
                    "is_low_power": structure.is_low_power,
                    "is_abandoned": structure.is_abandoned
                    or structure.is_maybe_abandoned,
                    "fuel_expires_at": structure.fuel_expires_at,
                    "services_offline": [
                        service.name
                        for service in structure.services.all()
                        if service.state != 2  # 2 = online
                    ],
                    "profile": (
                        profile_names.get(profile_id, f"#{profile_id}")
                        if profile_id
                        else None
                    ),
                }
            )
        corporation = owner.corporation
        owners.append(
            {
                "name": corporation.corporation_name,
                "ticker": corporation.corporation_ticker,
                "war_eligible": _war_eligible(corporation.corporation_id),
                "wars": _wars(owner, now),
                "last_update": owner.structures_last_update_at,
                "structures": structures,
            }
        )
    return owners


def _stamp(moment, style="R") -> str:
    return f"<t:{int(moment.timestamp())}:{style}>"


def build_embed(owners: list) -> Embed:
    now = timezone.now()
    level = 0  # 0 fine, 1 needs attention, 2 urgent
    lines = []
    fields = []
    for owner in owners:
        lines.append(f"**{owner['name']} [{owner['ticker']}]**")
        if owner["war_eligible"] is None:
            lines.append("War eligible: unknown (EVE did not answer)")
        elif owner["war_eligible"]:
            lines.append("War eligible: **yes** (wars can be declared on this corp)")
        else:
            lines.append("War eligible: no")
        if owner["wars"]:
            for war in owner["wars"]:
                level = 2
                if war["we_declared"]:
                    text = f"War: we declared war on **{war['other']}**"
                else:
                    text = f"War: **{war['other']}** declared war on us"
                text += f" on {war['declared']:%d %b %Y}."
                if war["fight_from"] > now:
                    text += f" Fighting starts {_stamp(war['fight_from'])}."
                else:
                    text += f" Fighting allowed since {_stamp(war['fight_from'], 'f')}."
                if war["ends"]:
                    text += f" War ends {_stamp(war['ends'])}."
                lines.append(f"\N{WARNING SIGN} {text}")
        else:
            lines.append("Wars: none declared or running")
        if owner["last_update"]:
            lines.append(f"Structure data read from EVE {_stamp(owner['last_update'])}")
        lines.append("")

        for structure in owner["structures"]:
            rows = []
            if structure["state"] == STATE_NORMAL:
                rows.append("State: shield vulnerable (normal)")
            else:
                level = 2
                state = f"\N{WARNING SIGN} State: **{structure['state_text'].upper()}**"
                if structure["state_timer_end"]:
                    state += f", timer ends {_stamp(structure['state_timer_end'])}"
                rows.append(state)

            if structure["is_abandoned"]:
                level = 2
                rows.append("\N{WARNING SIGN} Power: **ABANDONED**")
            elif structure["is_low_power"]:
                level = max(level, 1)
                rows.append("\N{WARNING SIGN} Power: **LOW POWER**")
            elif structure["is_full_power"]:
                rows.append("Power: full power")
            else:
                rows.append("Power: unknown")

            fuel = structure["fuel_expires_at"]
            if fuel is None:
                level = max(level, 1)
                rows.append("\N{WARNING SIGN} Fuel: **none**")
            else:
                text = f"Fuel: runs out {_stamp(fuel)} (EVE time {fuel:%a %d %b %H:%M})"
                if fuel - now < dt.timedelta(days=FUEL_WARNING_DAYS):
                    level = max(level, 1)
                    text = f"\N{WARNING SIGN} {text}"
                rows.append(text)

            if structure["services_offline"]:
                level = max(level, 1)
                offline = ", ".join(structure["services_offline"])
                rows.append(f"\N{WARNING SIGN} Services offline: {offline}")
            else:
                rows.append("Services: all online")

            if structure["profile"]:
                rows.append(f"Profile: {structure['profile']}")

            fields.append(
                (
                    f"{structure['name']} ({structure['type']}, {structure['system']})",
                    "\n".join(rows)[:1024],
                )
            )

    colour = (Color.green(), Color.orange(), Color.red())[level]
    embed = Embed(title=BOARD_TITLE, colour=colour)
    if not owners:
        embed.description = "No structure owner is registered on auth."
        return embed
    embed.description = "\n".join(lines).strip()[:4000]
    for name, value in fields[:25]:  # Discord allows 25 entries per message
        embed.add_field(name=name[:256], value=value, inline=False)
    return embed


class Structures(commands.Cog):
    """Structure and war overview for directors."""

    def __init__(self, bot):
        self.bot = bot
        self.board = Board(bot, BOARD_TITLE, "ORLOVBOT_STRUCTURE_BOARD_CHANNEL")

    @commands.Cog.listener()
    async def on_ready(self):
        # on_ready also fires after a reconnect, so only start the loop once
        if not self.update_board.is_running():
            self.update_board.start()

    def cog_unload(self):
        self.update_board.cancel()

    @tasks.loop(minutes=CHECK_MINUTES)
    async def update_board(self):
        if not getattr(settings, "ORLOVBOT_STRUCTURE_BOARD_CHANNEL", ""):
            return
        try:
            owners = await sync_to_async(collect)()
            await self.board.update(build_embed(owners))
        except Exception:
            # never let one failed round stop the loop
            logger.exception("Structure board update failed")
            self.board.reset()


def setup(bot):
    bot.add_cog(Structures(bot))
