"""Moon extractions of our own refineries, read from aa-moonmining.

Two things live here:
- /moons: lists the upcoming extractions on request.
- The moon board: one message in the channel named by ORLOVBOT_MOON_BOARD_CHANNEL that
  the bot keeps up to date, so nobody has to ask (docs/runbooks/09-moon-board.md).
"""

import logging

import discord
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Discord role that may use /moons (managed by Alliance Auth, see docs/design/membership.md)
MEMBER_ROLE = "Family Member"
MAX_ROWS = 10
BOARD_TITLE = "Upcoming moon extractions"
BOARD_CHECK_MINUTES = 10


async def build_embed() -> Embed:
    """The list of extractions that still have to pop or wait to be fractured."""
    from moonmining.models import Extraction

    now = timezone.now()
    extractions = (
        Extraction.objects.filter(auto_fracture_at__gte=now, canceled_at__isnull=True)
        .exclude(status__in=["CN", "CP"])  # canceled, completed
        .select_related("refinery", "refinery__moon__eve_moon")
        .order_by("chunk_arrival_at")
    )
    rows = [extraction async for extraction in extractions[:MAX_ROWS]]

    embed = Embed(title=BOARD_TITLE, colour=Color.blue())
    if not rows:
        embed.description = "No extraction is running at the moment."
        return embed

    for extraction in rows:
        refinery = extraction.refinery
        moon = refinery.moon.eve_moon.name if refinery.moon else "unknown moon"
        arrival = extraction.chunk_arrival_at
        stamp = int(arrival.timestamp())
        if arrival <= now:
            state = "Chunk has arrived, field can be fractured"
        else:
            # Discord renders <t:...:R> as a live countdown, no edit needed
            state = f"Chunk arrives <t:{stamp}:R>"
        embed.add_field(
            name=f"{refinery.name} ({moon})",
            value=(
                f"{state}\n"
                f"EVE time: {arrival:%a %d %b %H:%M}\n"
                f"Your time: <t:{stamp}:F>"
            ),
            inline=False,
        )
    return embed


def signature(embed) -> tuple:
    """What the board shows, for telling whether an edit is needed."""
    return (
        embed.description or "",
        tuple((field.name, field.value) for field in embed.fields),
    )


class Moons(commands.Cog):
    """Moon extraction overview."""

    def __init__(self, bot):
        self.bot = bot
        self._board_message = None
        self._board_signature = None
        self._warned_no_channel = False

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

    @tasks.loop(minutes=BOARD_CHECK_MINUTES)
    async def update_board(self):
        try:
            await self._update_board()
        except Exception:
            # never let one failed round stop the loop
            logger.exception("Moon board update failed")
            self._board_message = None

    async def _find_board_message(self, channel):
        async for message in channel.history(limit=50):
            if (
                message.author.id == self.bot.user.id
                and message.embeds
                and message.embeds[0].title == BOARD_TITLE
            ):
                return message
        return None

    async def _update_board(self):
        channel_name = getattr(settings, "ORLOVBOT_MOON_BOARD_CHANNEL", "")
        if not channel_name:
            return
        guild = self.bot.get_guild(int(settings.DISCORD_GUILD_ID))
        channel = (
            discord.utils.get(guild.text_channels, name=channel_name) if guild else None
        )
        if channel is None:
            if not self._warned_no_channel:
                logger.warning("Moon board: no text channel named #%s yet", channel_name)
                self._warned_no_channel = True
            return
        self._warned_no_channel = False

        embed = await build_embed()
        embed.set_footer(
            text=f"Kept up to date automatically, checked every {BOARD_CHECK_MINUTES} minutes"
        )

        if self._board_message is None:
            self._board_message = await self._find_board_message(channel)
            if self._board_message is not None:
                self._board_signature = signature(self._board_message.embeds[0])

        if self._board_message is None:
            self._board_message = await channel.send(embed=embed)
            self._board_signature = signature(embed)
            logger.info("Moon board posted in #%s", channel_name)
        elif signature(embed) != self._board_signature:
            try:
                await self._board_message.edit(embed=embed)
            except discord.NotFound:
                # somebody deleted the board; post a new one next round
                self._board_message = None
                return
            self._board_signature = signature(embed)
            logger.info("Moon board updated in #%s", channel_name)


def setup(bot):
    bot.add_cog(Moons(bot))
