"""Moon extractions of our own refineries, read from aa-moonmining.

Two things live here:
- /moons: lists the upcoming extractions on request.
- The moon board: one message in the channel named by ORLOVBOT_MOON_BOARD_CHANNEL that
  the bot keeps up to date, so nobody has to ask (docs/runbooks/09-moon-board.md).
- Public moons on a weekly timer (owner, 2026-10-25): ORLOVBOT_MOON_RECURRING lists them with
  a weekday and an EVE time; the board shows the next pop of each under the refineries.
- Public moons by date (owner, 2026-10-30): ORLOVBOT_MOON_SCHEDULE lists the published
  extractions of the freeport refineries, each with its own moment ("2026-11-04 17:00", EVE time);
  the board shows every one still to come, soonest first, with the chunk's arrival and the
  auto-pop three hours later, and keeps an entry for twelve hours after the pop (owner, 2026-11-06:
  people who missed a pop must still see which moon it was), in a "Popped, ore is out" section on top.
  The owner posts the game's Upcoming Extractions list whenever new ones are published.
"""

import datetime as dt
import logging

from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings
from django.utils import timezone

from orlovbot.board import CHECK_MINUTES, Board
from orlovbot.cogs.structures import _block, _stamp, _until

logger = logging.getLogger(__name__)

# Discord role that may use /moons (managed by Alliance Auth, see docs/design/membership.md)
MEMBER_ROLE = "Family Member"
MAX_ROWS = 10
BOARD_TITLE = "Upcoming moon extractions"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
POPPED = dt.timedelta(hours=12)  # a popped moon stays on the board this long (owner, 2026-11-06; three hours before that)
AUTO_POP = dt.timedelta(hours=3)  # a chunk auto-fractures three hours after it arrives (owner, 2026-10-30)


def next_pop(rule: dict, now) -> tuple:
    """(moment of the pop to show, popped already?) for a weekly rule {weekday 0=Monday, hour, minute}.
    A pop less than POPPED ago is shown as popped; otherwise the next one."""
    hour, minute = int(rule.get("hour", 0)), int(rule.get("minute", 0))
    day = now.date() - dt.timedelta(days=(now.weekday() - int(rule["weekday"])) % 7)
    at = dt.datetime.combine(day, dt.time(hour, minute), tzinfo=dt.timezone.utc)
    if now - at > POPPED:
        at += dt.timedelta(days=7)
    return at, at <= now


def recurring_entries(now) -> list:
    """[(moment, lines)] for the weekly public moons; the board sorts them in with the refineries."""
    rules = list(getattr(settings, "ORLOVBOT_MOON_RECURRING", []) or [])
    entries = []
    for rule in rules:
        at, popped = next_pop(rule, now)
        lines = []
        block = [("Tax:", "10% Tax - Pay to station owner", "boldblue", "")]  # public moons (owner, 2026-11-03)
        if popped:
            block.append(("Popped:", "ORE IS OUT", "green", f"since {at:%a %d %b %H:%M} EVE, listed until {at + POPPED:%H:%M}"))
        else:
            soon = at - now <= dt.timedelta(hours=1)
            block.append(("Pop:", _until(at, now), "orange" if soon else "blue", f"{at:%a %d %b %H:%M} EVE"))
        block.append(("Repeats:", f"every {WEEKDAYS[int(rule['weekday'])]} {int(rule.get('hour', 0)):02d}:{int(rule.get('minute', 0)):02d} EVE", "", ""))
        lines.append(f"### {rule['name']} ({rule.get('system', '')}, public moon)")
        lines.append(_block(block))
        entries.append((at, lines, popped))
    return entries


def parse_moment(text: str):
    """'2026-11-04 17:00' (EVE time, UTC) → aware datetime; None when it does not parse."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
        try:
            return dt.datetime.strptime(str(text).strip(), fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def scheduled_entries(now) -> list:
    """[(moment, lines, popped)] for the public moons published by date; a pop drops off POPPED after it happened."""
    entries = []
    for item in list(getattr(settings, "ORLOVBOT_MOON_SCHEDULE", []) or []):
        at = parse_moment(item.get("at", ""))
        if at is None:
            logger.warning("moon schedule: cannot read the moment of %s: %r", item.get("name"), item.get("at"))
            continue
        auto = at + AUTO_POP
        if now - auto > POPPED:
            continue
        block = [("Tax:", "10% Tax - Pay to station owner", "boldblue", "")]  # public moons (owner, 2026-11-03)
        if at <= now:
            block.append(("Arrives:", "ARRIVED", "green", f"since {at:%a %d %b %H:%M} EVE"))
        else:
            block.append(("Arrives:", _until(at, now), "blue", f"{at:%a %d %b %H:%M} EVE"))
        if auto <= now:
            block.append(("Popped:", "ORE IS OUT", "green", f"since {auto:%a %d %b %H:%M} EVE, listed until {auto + POPPED:%H:%M}"))
        else:
            soon = auto - now <= dt.timedelta(hours=1)
            block.append(("Auto-pop:", _until(auto, now), "orange" if soon else "blue", f"{auto:%a %d %b %H:%M} EVE"))
        lines = [f"### {item.get('name', 'Public moon')} ({item.get('system', '')}, public moon)", _block(block)]
        entries.append((auto if auto <= now else at, lines, auto <= now))
    return entries


async def build_embed() -> Embed:
    """The upcoming extractions, one block each in the structure board's style.

    Code blocks have no live countdown, so "in 2d 3h" is worked out at every check
    (the board refreshes every CHECK_MINUTES); the line under the block carries the
    live Discord timestamps in each reader's own time zone.
    """
    from moonmining.models import Extraction

    now = timezone.now()
    from django.db.models import Q

    # running extractions, plus the ones popped (fired by hand or auto-fractured) less than POPPED ago
    extractions = (
        Extraction.objects.filter(canceled_at__isnull=True)
        .exclude(status="CN")
        .filter(Q(auto_fracture_at__gte=now - POPPED) | Q(fractured_at__gte=now - POPPED))
        .select_related("refinery", "refinery__moon__eve_moon")
        .order_by("chunk_arrival_at")
    )
    rows = [extraction async for extraction in extractions[:MAX_ROWS]]
    entries = recurring_entries(now) + scheduled_entries(now)  # (moment, lines, popped): sorted together with the refineries, soonest first
    if not rows and not entries:
        embed = Embed(title=BOARD_TITLE, colour=Color.blue())
        embed.description = "No extraction is running at the moment."
        return embed

    ready = False
    for extraction in rows:
        refinery = extraction.refinery
        moon = refinery.moon.eve_moon.name if refinery.moon else "unknown moon"
        arrival = extraction.chunk_arrival_at
        auto = extraction.auto_fracture_at
        # NO TAX only on the refineries named in ORLOVBOT_MOON_NO_TAX; every other moon, including freeport refineries
        # we track and the public moons, carries the 10 % tax (owner, 2026-11-03)
        no_tax = any(n.lower() == refinery.name.lower() for n in getattr(settings, "ORLOVBOT_MOON_NO_TAX", []) or [])
        block = [("Tax:", "NO TAX - Tips to corp welcome", "boldgreen", "") if no_tax else ("Tax:", "10% Tax - Pay to station owner", "boldblue", "")]
        popped_at = extraction.fractured_at if extraction.fractured_at and extraction.fractured_at <= now else (auto if auto <= now else None)
        if popped_at is not None:
            # popped: the chunk was fired or fractured by itself; the entry stays POPPED long so latecomers see which moon it was
            block.append(("Popped:", "ORE IS OUT", "green", f"since {popped_at:%a %d %b %H:%M} EVE, listed until {popped_at + POPPED:%H:%M}"))
            entries.append((popped_at, [f"### {refinery.name} ({moon})", _block(block)], True))
            continue
        if arrival <= now:
            ready = True
            block.append(("Arrives:", "ARRIVED", "green", f"since {arrival:%a %d %b %H:%M} EVE"))
        else:
            block.append(("Arrives:", _until(arrival, now), "blue", f"{arrival:%a %d %b %H:%M} EVE"))
        if auto <= now:
            block.append(("Auto-pop:", "passed", "orange", ""))
        else:
            soon = auto - now <= dt.timedelta(hours=1)
            block.append(("Auto-pop:", f"{_until(auto, now)}", "orange" if soon else "blue", f"{auto:%a %d %b %H:%M} EVE"))
        lines = [f"### {refinery.name} ({moon})", _block(block)]
        entries.append((arrival, lines, False))
    # section headers (owner, 2026-11-03): what pops this week first, then one section per month with a known moon
    lines = []
    section = None
    week_end = now + dt.timedelta(days=7)
    for moment, block_lines, popped in sorted(entries, key=lambda x: x[0]):
        label = "Popped, ore is out" if popped else ("This week" if moment <= week_end else f"{moment:%B %Y}")
        if label != section:
            lines.append(f"## {label}")
            section = label
        lines.extend(block_lines)

    embed = Embed(title=BOARD_TITLE, colour=Color.green() if ready else Color.blue())
    embed.description = "\n".join(lines).strip()[:4096]
    return embed


class Moons(commands.Cog):
    """Moon extraction overview."""

    def __init__(self, bot):
        self.bot = bot
        self.board = Board(bot, BOARD_TITLE, "ORLOVBOT_MOON_BOARD_CHANNEL")

    @commands.Cog.listener()
    async def on_ready(self):
        # on_ready also fires after a reconnect, so only start the loop once
        if not self.update_board.is_running():
            self.update_board.start()

    def cog_unload(self):
        self.update_board.cancel()

    @commands.slash_command(
        name="moons",
        description="Upcoming moon extractions",
        guild_ids=[int(settings.DISCORD_GUILD_ID)],
    )
    async def moons(self, ctx):
        roles = getattr(ctx.author, "roles", [])
        if not any(role.name == MEMBER_ROLE for role in roles):
            return await ctx.respond(
                f"This command is for {MEMBER_ROLE}s.", ephemeral=True
            )
        return await ctx.respond(embed=await build_embed())

    @tasks.loop(minutes=CHECK_MINUTES)
    async def update_board(self):
        try:
            await self.board.update(await build_embed())
        except Exception:
            # never let one failed round stop the loop
            logger.exception("Moon board update failed")
            self.board.reset()


def setup(bot):
    bot.add_cog(Moons(bot))
