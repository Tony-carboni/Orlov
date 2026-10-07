"""The structure board: one message for directors with every structure we own.

On top a banner: green "NOT AT WAR", or red "AT WAR" while a war is declared or running.
Per structure: state, power mode, fuel left, offline services and the structure profile,
in colour: green as it should be, orange needs attention, red urgent, fuel blue while fine.
Per owning corp: the wars known from EVE notifications.
Data comes from aa-structures (which reads EVE every 30 minutes) plus one small read of
EVE's API of our own: the profile number per structure (with the structures token
aa-structures already holds). docs/runbooks/10-structure-board.md

Alerts: besides the board the bot posts a ping in the same channel when a new war appears
and when a war is over, and once a day per structure while its fuel is low or a service is
offline. What was
already sent is remembered in the Django cache (redis), so a bot restart does not ping again.
"""

import datetime as dt
import logging
import time

import discord
import requests
import yaml
from asgiref.sync import sync_to_async
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from orlovbot.board import CHECK_MINUTES, Board

logger = logging.getLogger(__name__)

BOARD_TITLE = "Structure status"
ESI = "https://esi.evetech.net/latest"
ESI_HEADERS = {"User-Agent": "orlov-auth structure board (allianceauth-discordbot cog)"}
ESI_CACHE_SECONDS = 3600  # profiles change rarely
# Discord cannot colour text, so the colour is a circle in front of a heading-sized line
BANNER_PEACE = "# \N{LARGE GREEN CIRCLE} NOT AT WAR"
BANNER_WAR = "# \N{LARGE RED CIRCLE} AT WAR"
# Coloured text exists in Discord only inside an "ansi" code block (fixed-width font, no
# links, no live timestamps). Green = as it should be, orange = needs attention, red = urgent.
ANSI = {"green": "0;32", "orange": "0;33", "red": "1;31", "blue": "0;34"}
LEVELS = {"orange": 1, "red": 2}  # how a text colour counts for the message's colour bar
LABEL_WIDTH = 11
REINFORCE_LABEL = "Reinforce:"
WAR_OVER_KEEP = dt.timedelta(hours=24)  # how long the "war over" message stays in the channel
FUEL_WARNING_DAYS = 7  # fuel shown in red, and the daily alert starts
FUEL_NOTICE_DAYS = 14  # fuel shown in orange
DATA_STALE_AFTER = dt.timedelta(minutes=90)  # aa-structures reads EVE every 30 minutes
STATE_NORMAL = 11  # aa-structures: shield vulnerable, the resting state of an Upwell structure
STRUCTURES_SCOPE = "esi-corporations.read_structures.v1"

ALERT_REPEAT = dt.timedelta(hours=24)  # low fuel / offline services: once a day while it lasts
ALERT_STATE_KEY = "orlovbot:structure-board:alerts"  # what was sent, kept in the cache
ALERT_TEST_KEY = "orlovbot:structure-board:test"  # set to make the bot post one test alert

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
                    "id": structure.id,
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
                    "reinforce_hour": structure.reinforce_hour,
                    "next_reinforce_hour": structure.next_reinforce_hour,
                    "next_reinforce_apply": structure.next_reinforce_apply,
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
                "corp_id": corporation.corporation_id,
                "name": corporation.corporation_name,
                "ticker": corporation.corporation_ticker,
                "wars": _wars(owner, now),
                "last_update": owner.structures_last_update_at,
                "structures": structures,
            }
        )
    return owners


def _stamp(moment, style="R") -> str:
    return f"<t:{int(moment.timestamp())}:{style}>"


def _paint(text: str, colour: str) -> str:
    return f"\u001b[{ANSI[colour]}m{text}\u001b[0m"


def _until(moment, now) -> str:
    """'in 2d 3h', worked out at each check because code blocks have no live countdown."""
    seconds = int((moment - now).total_seconds())
    if seconds <= 0:
        return "passed"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    if days:
        return f"in {days}d {hours}h"
    return f"in {hours}h {rest // 60}m"


def structure_rows(structure: dict, now) -> list:
    """The lines of one structure as (label, text, colour, note); colour None = plain."""
    rows = []
    if structure["state"] == STATE_NORMAL:
        rows.append(("State:", "shield vulnerable (normal)", "green", ""))
    else:
        note = ""
        if structure["state_timer_end"]:
            end = structure["state_timer_end"]
            note = f"timer ends {end:%d %b %H:%M} EVE, {_until(end, now)}"
        rows.append(("State:", structure["state_text"].upper(), "red", note))

    if structure["is_abandoned"]:
        rows.append(("Power:", "ABANDONED", "red", ""))
    elif structure["is_low_power"]:
        rows.append(("Power:", "LOW POWER", "orange", ""))
    elif structure["is_full_power"]:
        rows.append(("Power:", "full power", "green", ""))
    else:
        rows.append(("Power:", "unknown", "orange", ""))

    fuel = structure["fuel_expires_at"]
    if fuel is None:
        rows.append(("Fuel:", "none", "red", ""))
    else:
        left = fuel - now
        if left < dt.timedelta(days=FUEL_WARNING_DAYS):
            colour = "red"
        elif left < dt.timedelta(days=FUEL_NOTICE_DAYS):
            colour = "orange"
        else:
            colour = "blue"
        rows.append(("Fuel:", f"{_amount_left(fuel, now)} left", colour, ""))

    if structure["services_offline"]:
        offline = ", ".join(structure["services_offline"])
        rows.append(("Services:", f"offline: {offline}", "orange", ""))
    else:
        rows.append(("Services:", "all online", "green", ""))

    # The reinforcement hour (EVE time): the middle of the window in which the structure
    # leaves reinforcement. Green when it is the agreed hour, red when it is anything else.
    hour = structure.get("reinforce_hour")
    if hour is not None:
        required = getattr(settings, "ORLOVBOT_STRUCTURE_REINFORCE_HOUR", None)
        upcoming = structure.get("next_reinforce_hour")
        changing = upcoming is not None and upcoming != hour
        applies = structure.get("next_reinforce_apply")
        if changing and required is not None and upcoming == required:
            # The agreed hour is set and waits for the game's own delay: that is as good
            # as it gets, so it is shown as the agreed hour, in green, with the wait.
            note = f"from {applies:%d %b}, now {hour:02d}:00" if applies else f"pending, now {hour:02d}:00"
            rows.append((REINFORCE_LABEL, f"{upcoming:02d}:00 EVE", "green", note))
        else:
            note = ""
            if changing:
                note = f"to {upcoming:02d}:00" + (f" on {applies:%d %b}" if applies else "")
            # a scheduled change away from the agreed hour is as wrong as a wrong hour
            fine = hour == required and not changing
            colour = None if required is None else ("green" if fine else "red")
            rows.append((REINFORCE_LABEL, f"{hour:02d}:00 EVE", colour, note))

    if structure["profile"]:
        rows.append(("Profile:", structure["profile"], None, ""))
    return rows


def _block(rows: list) -> str:
    lines = []
    for label, text, colour, note in rows:
        line = f"{label:<{LABEL_WIDTH}}{_paint(text, colour) if colour else text}"
        if note:
            # plain text: the palette's only grey is too dark to read on Discord's dark theme
            line += f" ({note})"
        lines.append(line)
    return "```ansi\n" + "\n".join(lines) + "\n```"


def build_embed(owners: list) -> Embed:
    now = timezone.now()
    level = 0  # 0 fine, 1 needs attention, 2 urgent
    at_war = any(owner["wars"] for owner in owners)
    lines = [BANNER_WAR if at_war else BANNER_PEACE, ""]
    for owner in owners:
        lines.append(f"**{owner['name']} [{owner['ticker']}]**")
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
        # normally silent: the board's "Last checked" entry is the one time shown
        last_update = owner["last_update"]
        if last_update is None or now - last_update > DATA_STALE_AFTER:
            level = max(level, 1)
            age = f"last read {_stamp(last_update)}" if last_update else "never read"
            lines.append(f"\N{WARNING SIGN} Structure data from EVE is old: {age}")

        for structure in owner["structures"]:
            rows = structure_rows(structure, now)
            for _, _, colour, _ in rows:
                level = max(level, LEVELS.get(colour, 0))
            # a small heading: one step larger than bold text
            lines.append(
                f"### {structure['name']} ({structure['type']}, {structure['system']})"
            )
            lines.append(_block(rows))

    colour = (Color.green(), Color.orange(), Color.red())[level]
    embed = Embed(title=BOARD_TITLE, colour=colour)
    if not owners:
        embed.description = "No structure owner is registered on auth."
        return embed
    embed.description = "\n".join(lines).strip()[:4096]
    return embed


def _amount_left(fuel, now) -> str:
    left = fuel - now
    if left >= dt.timedelta(days=2):
        return f"{left.days} days"
    return f"{max(int(left.total_seconds() // 3600), 0)} hours"


def structure_problems(structure: dict, now) -> dict:
    """The things worth a daily ping, by kind: 'fuel' and 'services'."""
    problems = {}
    fuel = structure["fuel_expires_at"]
    if fuel is not None and fuel - now < dt.timedelta(days=FUEL_WARNING_DAYS):
        problems["fuel"] = (
            f"Fuel: **{_amount_left(fuel, now)} left**, runs out {_stamp(fuel, 'F')}"
        )
    elif fuel is None and structure["is_low_power"]:
        problems["fuel"] = "Fuel: **none**, the structure is in low power"
    if structure["services_offline"]:
        offline = ", ".join(structure["services_offline"])
        problems["services"] = f"Services offline: **{offline}**"
    return problems


def plan_alerts(owners: list, state: dict, now) -> tuple:
    """Decide which alerts to send or remove. Pure: no Discord, no cache.

    state maps an alert key to what was sent for it. Returns (actions, new_state);
    an action is ("send", key, text, old_message_id) or ("delete", key, message_id).
    """
    mention = getattr(settings, "ORLOVBOT_STRUCTURE_ALERT_MENTION", "@everyone")
    actions = []
    new_state = {}
    for owner in owners:
        for war in owner["wars"]:
            key = (
                f"war:{owner['corp_id']}:{war['by']}:{war['against']}:"
                f"{int(war['declared'].timestamp())}"
            )
            if key in state:
                new_state[key] = state[key]
                continue
            us = f"**{owner['name']} [{owner['ticker']}]**"
            if war["we_declared"]:
                text = f"{us} declared war on **{war['other']}**."
            else:
                text = f"**{war['other']}** declared war on {us}."
            if war["fight_from"] > now:
                text += (
                    f" Fighting starts {_stamp(war['fight_from'])}"
                    f" ({_stamp(war['fight_from'], 'F')})."
                )
            else:
                text += f" Fighting is allowed since {_stamp(war['fight_from'], 'F')}."
            actions.append(("send", key, f"{mention} **War declared.** {text}", None))
            # the names are kept for the "war over" message, when the war itself is gone
            new_state[key] = {
                "message_id": None,
                "us": us,
                "other": war["other"],
            }

        for structure in owner["structures"]:
            key = f"structure:{structure['id']}"
            entry = state.get(key)
            problems = structure_problems(structure, now)
            if not problems:
                continue  # an old alert, if any, is removed below
            sent = dict(entry["kinds"]) if entry else {}
            # a kind that cleared is forgotten, so it pings at once if it comes back
            sent = {kind: when for kind, when in sent.items() if kind in problems}
            due = [
                kind
                for kind in problems
                if kind not in sent
                or now - dt.datetime.fromisoformat(sent[kind]) >= ALERT_REPEAT
            ]
            if not due:
                new_state[key] = {"kinds": sent, "message_id": entry["message_id"]}
                continue
            lines = "\n".join(f"- {text}" for text in problems.values())
            text = (
                f"{mention} **{structure['name']}** ({structure['type']}, "
                f"{structure['system']}) needs attention:\n{lines}"
            )
            old_message_id = entry["message_id"] if entry else None
            actions.append(("send", key, text, old_message_id))
            new_state[key] = {
                "kinds": {kind: now.isoformat() for kind in problems},
                "message_id": None,
            }

    # A war that is gone: ping once that it is over. The message replaces the declaration
    # and is removed after WAR_OVER_KEEP.
    registered = {owner["corp_id"] for owner in owners}
    for key, entry in state.items():
        if key in new_state:
            continue
        if key.startswith("war:"):
            if int(key.split(":")[1]) not in registered:
                # the corp dropped off the board (token trouble), which is not peace
                new_state[key] = entry
                continue
            if entry.get("us") and entry.get("other"):
                text = f"The war between {entry['us']} and **{entry['other']}** has ended."
            else:
                text = "A war has ended."
            over_key = "warover:" + key[len("war:"):]
            actions.append(
                ("send", over_key, f"{mention} **War over.** {text}", entry.get("message_id"))
            )
            new_state[over_key] = {
                "message_id": None,
                "until": (now + WAR_OVER_KEEP).isoformat(),
            }
        elif key.startswith("warover:") and now < dt.datetime.fromisoformat(entry["until"]):
            new_state[key] = entry

    # whatever is no longer a problem (fuel topped up, test done, old "war over"): remove its alert
    for key, entry in state.items():
        if key not in new_state and not key.startswith("war:"):
            actions.append(("delete", key, entry.get("message_id")))
    return actions, new_state


def load_alert_state() -> dict:
    return cache.get(ALERT_STATE_KEY) or {}


def save_alert_state(state: dict) -> None:
    cache.set(ALERT_STATE_KEY, state, timeout=None)


def pop_test_request() -> bool:
    requested = bool(cache.get(ALERT_TEST_KEY))
    if requested:
        cache.delete(ALERT_TEST_KEY)
    return requested


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
            return
        if getattr(settings, "ORLOVBOT_STRUCTURE_ALERTS", True):
            try:
                await self._send_alerts(owners)
            except Exception:
                logger.exception("Structure alerts failed")

    async def _send_alerts(self, owners: list):
        channel = self.board.get_channel()
        if channel is None:
            return
        state = await sync_to_async(load_alert_state)()
        actions, new_state = plan_alerts(owners, state, timezone.now())
        if await sync_to_async(pop_test_request)():
            mention = getattr(settings, "ORLOVBOT_STRUCTURE_ALERT_MENTION", "@everyone")
            text = (
                f"{mention} Test alert from the structure board. Nothing is wrong; "
                "the bot removes this message at its next check."
            )
            actions.append(("send", "test", text, None))
            new_state["test"] = {"message_id": None}
        if not actions:
            return
        # Remember first, send second: if anything goes wrong after this point the worst
        # case is one missed ping, never the same ping every 10 minutes.
        await sync_to_async(save_alert_state)(new_state)
        for action in actions:
            if action[0] == "send":
                _, key, text, old_message_id = action
                await self._delete_message(channel, old_message_id)
                try:
                    message = await channel.send(
                        text, allowed_mentions=discord.AllowedMentions(everyone=True)
                    )
                except discord.HTTPException:
                    logger.exception("Structure alert %s could not be sent", key)
                    # forget it again so the next check retries
                    if key in state:
                        new_state[key] = state[key]
                    else:
                        new_state.pop(key, None)
                    war_key = "war:" + key[len("warover:"):]
                    if key.startswith("warover:") and war_key in state:
                        # put the war back, so its end is noticed and announced again
                        new_state[war_key] = {**state[war_key], "message_id": None}
                    continue
                new_state[key]["message_id"] = message.id
                logger.info("Structure alert sent: %s", key)
            else:
                _, key, message_id = action
                await self._delete_message(channel, message_id)
                logger.info("Structure alert cleared: %s", key)
        await sync_to_async(save_alert_state)(new_state)

    @staticmethod
    async def _delete_message(channel, message_id):
        if not message_id:
            return
        try:
            await channel.get_partial_message(message_id).delete()
        except discord.HTTPException:
            pass  # already gone, or not ours to delete


def setup(bot):
    bot.add_cog(Structures(bot))
