"""Moon extractions of our own refineries, read from aa-moonmining.

Two things live here:
- /moons: lists the upcoming extractions on request.
- The moon board: one message in the channel named by ORLOVBOT_MOON_BOARD_CHANNEL that
  the bot keeps up to date, so nobody has to ask (docs/runbooks/09-moon-board.md).
- Public moons on a weekly timer (owner, 2026-10-25): ORLOVBOT_MOON_RECURRING lists them with
  a weekday and an EVE time; the board shows the next pop of each under the refineries.
- Public moons by date (owner, 2026-10-30): ORLOVBOT_MOON_SCHEDULE lists the published
  extractions of the freeport refineries, each with its own moment ("2026-11-04 17:00", EVE time);
  the board shows every one still to come, soonest first, and keeps a pop for three hours after.
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
RECENT = dt.timedelta(hours=3)  # a weekly pop stays on the board this long after it happened


def next_pop(rule: dict, now) -> tuple:
    """(moment of the pop to show, popped already?) for a weekly rule {weekday 0=Monday, hour, minute}.
    A pop less than RECENT ago is shown as popped; otherwise the next one."""
    hour, minute = int(rule.get("hour", 0)), int(rule.get("minute", 0))
    day = now.date() - dt.timedelta(days=(now.weekday() - int(rule["weekday"])) % 7)
    at = dt.datetime.combine(day, dt.time(hour, minute), tzinfo=dt.timezone.utc)
    if now - at > RECENT:
        at += dt.timedelta(days=7)
    return at, at <= now


def recurring_entries(now) -> list:
    """[(moment, lines)] for the weekly public moons; the board sorts them in with the refineries."""
    rules = list(getattr(settings, "ORLOVBOT_MOON_RECURRING", []) or [])
    entries = []
    for rule in rules:
        at, popped = next_pop(rule, now)
        lines = []
        block = []
        if popped:
            block.append(("Pop:", "POPPED, ore is out", "green", f"since {at:%a %d %b %H:%M} EVE"))
        else:
            soon = at - now <= dt.timedelta(hours=1)
            block.append(("Pop:", _until(at, now), "orange" if soon else "blue", f"{at:%a %d %b %H:%M} EVE"))
        block.append(("Repeats:", f"every {WEEKDAYS[int(rule['weekday'])]} {int(rule.get('hour', 0)):02d}:{int(rule.get('minute', 0)):02d} EVE", "", ""))
        lines.append(f"### {rule['name']} ({rule.get('system', '')}, public moon)")
        lines.append(_block(block))
        lines.append(f"Your time: pops {_stamp(at, 'f')}")
        lines.append("")
        entries.append((at, lines))
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
    """[(moment, lines)] for the public moons published by date; past pops drop off RECENT after they happened."""
    entries = []
    for item in list(getattr(settings, "ORLOVBOT_MOON_SCHEDULE", []) or []):
        at = parse_moment(item.get("at", ""))
        if at is None:
            logger.warning("moon schedule: cannot read the moment of %s: %r", item.get("name"), item.get("at"))
            continue
        if now - at > RECENT:
            continue
        block = []
        if at <= now:
            block.append(("Pop:", "POPPED, ore is out", "green", f"since {at:%a %d %b %H:%M} EVE"))
        else:
            soon = at - now <= dt.timedelta(hours=1)
            block.append(("Pop:", _until(at, now), "orange" if soon else "blue", f"{at:%a %d %b %H:%M} EVE"))
        lines = [f"### {item.get('name', 'Public moon')} ({item.get('system', '')}, public moon)", _block(block),
                 f"Your time: pops {_stamp(at, 'f')}", ""]
        entries.append((at, lines))
    return entries


async def build_embed() -> Embed:
    """The upcoming extractions, one block each in the structure board's style.

    Code blocks have no live countdown, so "in 2d 3h" is worked out at every check
    (the board refreshes every CHECK_MINUTES); the line under the block carries the
    live Discord timestamps in each reader's own time zone.
    """
    from moonmining.models import Extraction

    now = timezone.now()
    extractions = (
        Extraction.objects.filter(auto_fracture_at__gte=now, canceled_at__isnull=True)
        .exclude(status__in=["CN", "CP"])  # canceled, completed
        .select_related("refinery", "refinery__moon__eve_moon")
        .order_by("chunk_arrival_at")
    )
    rows = [extraction async for extraction in extractions[:MAX_ROWS]]
    entries = recurring_entries(now) + scheduled_entries(now)  # (moment, lines): sorted together with the refineries, soonest first
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
        block = []
        if arrival <= now:
            ready = True
            block.append(("Chunk:", "ARRIVED, can be fractured", "green", f"since {arrival:%a %d %b %H:%M} EVE"))
        else:
            block.append(("Chunk:", f"arrives {_until(arrival, now)}", "blue", f"{arrival:%a %d %b %H:%M} EVE"))
        if auto <= now:
            block.append(("Auto-pop:", "passed", "orange", ""))
        else:
            soon = auto - now <= dt.timedelta(hours=1)
            block.append(("Auto-pop:", f"{_until(auto, now)}", "orange" if soon else "blue", f"{auto:%a %d %b %H:%M} EVE"))
        lines = [f"### {refinery.name} ({moon})", _block(block)]
        # live timestamps: Discord shows these in the reader's own time zone
        lines.append(f"Your time: arrives {_stamp(arrival, 'f')} · auto-pops {_stamp(auto, 'f')}")
        lines.append("")
        entries.append((arrival, lines))
    lines = [line for _, block_lines in sorted(entries, key=lambda x: x[0]) for line in block_lines]

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
