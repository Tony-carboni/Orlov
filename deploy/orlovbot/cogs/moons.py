"""/moons: the upcoming moon extractions of our own refineries, read from aa-moonmining."""

import logging

from discord import Color, Embed
from discord.ext import commands

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Discord role that may use the command (managed by Alliance Auth, see docs/design/membership.md)
MEMBER_ROLE = "Family Member"
MAX_ROWS = 10


class Moons(commands.Cog):
    """Moon extraction overview."""

    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(
        name="moons",
        description="Upcoming moon extractions",
        guild_ids=[int(settings.DISCORD_GUILD_ID)],
    )
    async def moons(self, ctx):
        from moonmining.models import Extraction

        roles = getattr(ctx.author, "roles", [])
        if not any(role.name == MEMBER_ROLE for role in roles):
            return await ctx.respond(
                f"This command is for {MEMBER_ROLE}s.", ephemeral=True
            )

        now = timezone.now()
        # Still to pop, or popped and not yet auto-fractured. Ordered by arrival.
        extractions = (
            Extraction.objects.filter(
                auto_fracture_at__gte=now, canceled_at__isnull=True
            )
            .exclude(status__in=["CN", "CP"])  # canceled, completed
            .select_related("refinery", "refinery__moon__eve_moon")
            .order_by("chunk_arrival_at")
        )
        rows = [extraction async for extraction in extractions[:MAX_ROWS]]

        embed = Embed(title="Upcoming moon extractions", colour=Color.blue())
        if not rows:
            embed.description = "No extraction is running at the moment."
            return await ctx.respond(embed=embed)

        for extraction in rows:
            refinery = extraction.refinery
            moon = refinery.moon.eve_moon.name if refinery.moon else "unknown moon"
            arrival = extraction.chunk_arrival_at
            stamp = int(arrival.timestamp())
            if arrival <= now:
                state = "Chunk has arrived, field can be fractured"
            else:
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
        return await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Moons(bot))
