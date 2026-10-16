"""Moon extractions of our own refineries, read from aa-moonmining.

Two things live here:
- /moons: lists the upcoming extractions on request.
- The moon board: one message in the channel named by ORLOVBOT_MOON_BOARD_CHANNEL that
  the bot keeps up to date, so nobody has to ask (docs/runbooks/09-moon-board.md).
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
    if not rows:
        embed = Embed(title=BOARD_TITLE, colour=Color.blue())
        embed.description = "No extraction is running at the moment."
        return embed

    lines = []
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
        lines.append(f"### {refinery.name} ({moon})")
        lines.append(_block(block))
        # live timestamps: Discord shows these in the reader's own time zone
        lines.append(f"Your time: arrives {_stamp(arrival, 'f')} · auto-pops {_stamp(auto, 'f')}")
        lines.append("")

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
