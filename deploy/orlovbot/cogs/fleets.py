"""Planned fleets: a board of upcoming fleets in #planned-fleets, fed by /fleet commands (owner, 2026-11-09;
docs/runbooks/22-planned-fleets.md).

- /fleet add name type when where [fc] [info]   adds a fleet; "when" is EVE time, e.g. "11/11 19:00", "tomorrow 20:00"
- /fleet edit number [name] [type] [when] [where] [fc] [info]   changes fields of a fleet
- /fleet remove number                            takes a fleet off the board
- /fleet list                                     the same list as a private reply

The board is one message the bot keeps editing (orlovbot.board.Board), in the moon board's style: a heading per
fleet and an ansi block with the countdown, formup place, FC and extra info, then a live Discord timestamp in the
reader's own time zone. A fleet stays listed ORLOVBOT_FLEET_KEEP_HOURS after its formup, then drops off.
The list lives in the Django cache (redis, written to disk) like the kill feed's memory of what it posted.

Settings (conf/local.py):
- ORLOVBOT_FLEET_BOARD_CHANNEL   channel name; "" switches the board off
- ORLOVBOT_FLEET_ROLES           roles that may add and edit fleets (["Family Member"] once the experiment is over)
- ORLOVBOT_FLEET_ADMIN_ROLES     roles that may remove or edit anyone's fleet; the creator may always
- ORLOVBOT_FLEET_KEEP_HOURS      hours a fleet stays listed after its formup time
"""

import datetime as dt
import logging
import re

import discord
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from orlovbot.board import CHECK_MINUTES, Board
from orlovbot.cogs.structures import _block, _stamp, _until

logger = logging.getLogger(__name__)

BOARD_TITLE = "Planned fleets"
CACHE_KEY = "orlovbot:fleets"  # {"next_id": int, "fleets": [dict]}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WHEN_HELP = "EVE time: 11/11 19:00, tomorrow 20:00, sat 18:00, or 19:00 for today"  # under 100 characters: Discord's limit for an option description


# --- settings -------------------------------------------------------------------------------------------------------
def _roles(name: str, default: list) -> list:
    return [str(r) for r in (getattr(settings, name, None) or default)]


def keep_hours() -> float:
    return float(getattr(settings, "ORLOVBOT_FLEET_KEEP_HOURS", 3) or 3)


# --- the list in the cache --------------------------------------------------------------------------------------------
def load() -> dict:
    data = cache.get(CACHE_KEY) or {}
    return {"next_id": int(data.get("next_id", 1)), "fleets": list(data.get("fleets", []))}


def save(data: dict) -> None:
    cache.set(CACHE_KEY, data, timeout=None)


def fleet_time(fleet: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(fleet["at"])


def upcoming(data: dict, now) -> list:
    """The fleets still worth showing, soonest first; the ones past formup by more than keep_hours are dropped."""
    limit = now - dt.timedelta(hours=keep_hours())
    rows = [f for f in data["fleets"] if fleet_time(f) >= limit]
    return sorted(rows, key=fleet_time)


# --- reading "when" -----------------------------------------------------------------------------------------------------
_TIME = r"(?P<h>\d{1,2})(?:[:.h](?P<m>\d{2}))?\s*(?:eve|evetime|utc)?"
_DMY = re.compile(r"^(?P<d>\d{1,2})[/.-](?P<mo>\d{1,2})(?:[/.-](?P<y>\d{2,4}))?\s*[-,]?\s+" + _TIME + r"$")
_ISO = re.compile(r"^(?P<y>\d{4})-(?P<mo>\d{1,2})-(?P<d>\d{1,2})\s*[-,]?\s+" + _TIME + r"$")
_WORD = re.compile(r"^(?P<word>today|tonight|tomorrow|tmrw|" + "|".join(WEEKDAYS) + r"|" + "|".join(w[:3] for w in WEEKDAYS) + r")\s*[-,]?\s+" + _TIME + r"$")


def parse_when(text: str, now) -> dt.datetime | None:
    """'11/11 19:00' (day/month, EVE time), '11/11/2026 19.00', '2026-11-11 19:00', 'tomorrow 20:00', 'sat 18:00'.
    A date without a year means the next occurrence: this year, or next year when that day has passed."""
    s = re.sub(r"\s+", " ", str(text).strip().lower())
    s = re.sub(r"\b(at|@)\b", " ", s).strip()
    m = _ISO.match(s) or _DMY.match(s)
    if m:
        try:
            hour, minute = int(m.group("h")), int(m.group("m") or 0)
            year = m.group("y")
            if year is not None:
                year = int(year)
                year = year + 2000 if year < 100 else year
                return dt.datetime(year, int(m.group("mo")), int(m.group("d")), hour, minute, tzinfo=dt.timezone.utc)
            at = dt.datetime(now.year, int(m.group("mo")), int(m.group("d")), hour, minute, tzinfo=dt.timezone.utc)
            if at < now - dt.timedelta(days=1):
                at = at.replace(year=now.year + 1)
            return at
        except ValueError:
            return None
    m = _WORD.match(s) or re.match(r"^(?P<word>)" + _TIME + r"$", s)  # a bare time means today, or tomorrow once that hour has passed
    if m:
        try:
            hour, minute = int(m.group("h")), int(m.group("m") or 0)
            word = m.group("word")
            day = now.date()
            if word in ("tomorrow", "tmrw"):
                day += dt.timedelta(days=1)
            elif word == "" and dt.datetime.combine(day, dt.time(hour, minute), tzinfo=dt.timezone.utc) < now:
                day += dt.timedelta(days=1)
            elif word not in ("", "today", "tonight"):
                target = next(i for i, w in enumerate(WEEKDAYS) if w.startswith(word[:3]))
                ahead = (target - now.weekday()) % 7
                day += dt.timedelta(days=ahead)
                if ahead == 0 and dt.datetime.combine(day, dt.time(hour, minute), tzinfo=dt.timezone.utc) < now:
                    day += dt.timedelta(days=7)
            return dt.datetime.combine(day, dt.time(hour, minute), tzinfo=dt.timezone.utc)
        except (ValueError, StopIteration):
            return None
    return None


def clean_name(member) -> str:
    """The caller's display name without the '[TICKER] ' prefix auth puts in front."""
    return re.sub(r"^\[[^\]]+\]\s*", "", getattr(member, "display_name", "") or "").strip() or "unknown"


# --- the board ------------------------------------------------------------------------------------------------------
def fleet_lines(fleet: dict, now) -> list:
    at = fleet_time(fleet)
    block = []
    if at <= now:
        block.append(("Formup:", "FORMING UP NOW", "boldgreen", f"since {at:%a %d %b %H:%M} EVE"))
    else:
        soon = at - now <= dt.timedelta(hours=1)
        block.append(("Formup:", _until(at, now), "orange" if soon else "blue", f"{at:%a %d %b %H:%M} EVE"))
    block.append(("Where:", fleet.get("where") or "-", "", ""))
    block.append(("FC:", fleet.get("fc") or "-", "", ""))
    if fleet.get("info"):
        block.append(("Info:", fleet["info"], "", ""))
    kind = f" ({fleet['type']})" if fleet.get("type") else ""
    return [
        f"### {fleet['name']}{kind}",
        _block(block),
        f"Your time: {_stamp(at, 'f')} ({_stamp(at, 'R')}) · fleet #{fleet['id']}",
    ]


def build_embed() -> Embed:
    now = timezone.now()
    rows = upcoming(load(), now)
    if not rows:
        embed = Embed(title=BOARD_TITLE, colour=Color.blue())
        embed.description = "No fleets planned at the moment. Add one with `/fleet add`."
        return embed
    lines = []
    section = None
    today_end = dt.datetime.combine(now.date(), dt.time.max, tzinfo=dt.timezone.utc)
    week_end = now + dt.timedelta(days=7)
    forming = False
    for fleet in rows:
        at = fleet_time(fleet)
        if at <= now:
            label = "Forming up now"
            forming = True
        elif at <= today_end:
            label = "Today"
        elif at <= week_end:
            label = "This week"
        else:
            label = f"{at:%B %Y}"
        if label != section:
            lines.append(f"## {label}")
            section = label
        lines.extend(fleet_lines(fleet, now))
    embed = Embed(title=BOARD_TITLE, colour=Color.green() if forming else Color.blue())
    embed.description = "\n".join(lines).strip()[:4096]
    embed.set_footer(text="Times in the blocks are EVE time. Add a fleet with /fleet add, remove with /fleet remove.")
    return embed


# --- the cog -----------------------------------------------------------------------------------------------------------
class Fleets(commands.Cog):
    """Planned fleets board and the /fleet commands."""

    fleet = discord.SlashCommandGroup("fleet", "Planned fleets", guild_ids=[int(settings.DISCORD_GUILD_ID)])

    def __init__(self, bot):
        self.bot = bot
        self.board = Board(bot, BOARD_TITLE, "ORLOVBOT_FLEET_BOARD_CHANNEL")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.update_board.is_running():
            self.update_board.start()

    def cog_unload(self):
        self.update_board.cancel()

    # --- helpers ------------------------------------------------------------------------------------------------------
    @staticmethod
    def _has(ctx, roles: list) -> bool:
        return any(role.name in roles for role in getattr(ctx.author, "roles", []))

    def _may_use(self, ctx) -> bool:
        return self._has(ctx, _roles("ORLOVBOT_FLEET_ROLES", ["Family Member"]) + _roles("ORLOVBOT_FLEET_ADMIN_ROLES", ["Alliance Director"]))

    def _may_change(self, ctx, fleet: dict) -> bool:
        return fleet.get("by") == ctx.author.id or self._has(ctx, _roles("ORLOVBOT_FLEET_ADMIN_ROLES", ["Alliance Director"]))

    async def _refresh(self):
        try:
            await self.board.update(build_embed())
        except Exception:
            logger.exception("Fleet board update failed")
            self.board.reset()

    @staticmethod
    def _find(data: dict, number: int):
        return next((f for f in data["fleets"] if f["id"] == number), None)

    @staticmethod
    def _summary(fleet: dict) -> str:
        at = fleet_time(fleet)
        kind = f" ({fleet['type']})" if fleet.get("type") else ""
        return f"**#{fleet['id']} {fleet['name']}**{kind}: {at:%a %d %b %H:%M} EVE ({_stamp(at, 'f')} for you), {fleet.get('where') or '-'}, FC {fleet.get('fc') or '-'}"

    # --- commands -----------------------------------------------------------------------------------------------------
    @fleet.command(name="add", description="Put a fleet on the planned fleets board")
    async def add(
        self,
        ctx,
        name: discord.Option(str, "Fleet name, e.g. Thera camp"),  # noqa: B008
        type: discord.Option(str, "PVP, PVE, mining, structure op, roam ..."),  # noqa: A002, B008
        when: discord.Option(str, WHEN_HELP),  # noqa: B008
        where: discord.Option(str, "Formup place, e.g. Jita 4-4"),  # noqa: B008
        fc: discord.Option(str, "Fleet commander; you when left out", required=False) = None,  # noqa: B008
        info: discord.Option(str, "Extra info: ships, doctrine, comms ...", required=False) = None,  # noqa: B008
    ):
        if not self._may_use(ctx):
            return await ctx.respond("Planning fleets is for " + ", ".join(_roles("ORLOVBOT_FLEET_ROLES", ["Family Member"])) + ".", ephemeral=True)
        now = timezone.now()
        at = parse_when(when, now)
        if at is None:
            return await ctx.respond(f"I cannot read the time `{when}`. Try it as {WHEN_HELP}.", ephemeral=True)
        if at < now - dt.timedelta(hours=keep_hours()):
            return await ctx.respond(f"{at:%a %d %b %H:%M} EVE is already in the past.", ephemeral=True)
        data = load()
        fleet = {
            "id": data["next_id"],
            "name": name.strip()[:80],
            "type": (type or "").strip()[:40],
            "at": at.isoformat(),
            "where": where.strip()[:80],
            "fc": (fc or clean_name(ctx.author)).strip()[:60],
            "info": (info or "").strip()[:300],
            "by": ctx.author.id,
            "created": now.isoformat(),
        }
        data["next_id"] += 1
        data["fleets"].append(fleet)
        save(data)
        logger.info("fleets: #%s %s added by %s for %s", fleet["id"], fleet["name"], ctx.author, at)
        await ctx.respond("Added to the board: " + self._summary(fleet) + f"\nRemove it later with `/fleet remove {fleet['id']}`.", ephemeral=True)
        await self._refresh()

    @fleet.command(name="edit", description="Change a planned fleet; give only the fields that change")
    async def edit(
        self,
        ctx,
        number: discord.Option(int, "The fleet number shown on the board", min_value=1),  # noqa: B008
        name: discord.Option(str, "New name", required=False) = None,  # noqa: B008
        type: discord.Option(str, "New type", required=False) = None,  # noqa: A002, B008
        when: discord.Option(str, WHEN_HELP, required=False) = None,  # noqa: B008
        where: discord.Option(str, "New formup place", required=False) = None,  # noqa: B008
        fc: discord.Option(str, "New fleet commander", required=False) = None,  # noqa: B008
        info: discord.Option(str, "New extra info; a single - clears it", required=False) = None,  # noqa: B008
    ):
        if not self._may_use(ctx):
            return await ctx.respond("Planning fleets is for " + ", ".join(_roles("ORLOVBOT_FLEET_ROLES", ["Family Member"])) + ".", ephemeral=True)
        data = load()
        fleet = self._find(data, number)
        if fleet is None:
            return await ctx.respond(f"There is no fleet #{number} on the board.", ephemeral=True)
        if not self._may_change(ctx, fleet):
            return await ctx.respond(f"Fleet #{number} was added by someone else; only they or an admin can change it.", ephemeral=True)
        if when is not None:
            at = parse_when(when, timezone.now())
            if at is None:
                return await ctx.respond(f"I cannot read the time `{when}`. Try it as {WHEN_HELP}.", ephemeral=True)
            fleet["at"] = at.isoformat()
        for key, value, width in (("name", name, 80), ("type", type, 40), ("where", where, 80), ("fc", fc, 60), ("info", info, 300)):
            if value is not None:
                fleet[key] = "" if value.strip() == "-" else value.strip()[:width]
        save(data)
        logger.info("fleets: #%s edited by %s", number, ctx.author)
        await ctx.respond("Changed: " + self._summary(fleet), ephemeral=True)
        await self._refresh()

    @fleet.command(name="remove", description="Take a fleet off the planned fleets board")
    async def remove(self, ctx, number: discord.Option(int, "The fleet number shown on the board", min_value=1)):  # noqa: B008
        if not self._may_use(ctx):
            return await ctx.respond("Planning fleets is for " + ", ".join(_roles("ORLOVBOT_FLEET_ROLES", ["Family Member"])) + ".", ephemeral=True)
        data = load()
        fleet = self._find(data, number)
        if fleet is None:
            return await ctx.respond(f"There is no fleet #{number} on the board.", ephemeral=True)
        if not self._may_change(ctx, fleet):
            return await ctx.respond(f"Fleet #{number} was added by someone else; only they or an admin can remove it.", ephemeral=True)
        data["fleets"] = [f for f in data["fleets"] if f["id"] != number]
        save(data)
        logger.info("fleets: #%s %s removed by %s", number, fleet["name"], ctx.author)
        await ctx.respond(f"Removed #{number} {fleet['name']} from the board.", ephemeral=True)
        await self._refresh()

    @fleet.command(name="list", description="The planned fleets, as a private reply")
    async def list_(self, ctx):
        rows = upcoming(load(), timezone.now())
        if not rows:
            return await ctx.respond("No fleets planned at the moment.", ephemeral=True)
        await ctx.respond("\n".join(self._summary(f) for f in rows)[:1900], ephemeral=True)

    # --- the loop -----------------------------------------------------------------------------------------------------
    @tasks.loop(minutes=CHECK_MINUTES)
    async def update_board(self):
        await self._refresh()


def setup(bot):
    bot.add_cog(Fleets(bot))
