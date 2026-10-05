"""A board: one message in a channel that the bot keeps up to date by editing it in place.

Used by the moon board (cogs/moons.py) and the structure board (cogs/structures.py).
"""

import logging
import time

import discord

from django.conf import settings

logger = logging.getLogger(__name__)

CHECK_MINUTES = 10
# The last entry of every board: when the bot last looked. If it is much older than
# CHECK_MINUTES the bot is not running.
LAST_CHECKED = "Last checked"


def signature(embed) -> tuple:
    """What a board shows, apart from the "last checked" time, for telling whether it changed."""
    colour = embed.colour.value if embed.colour else None
    return (
        embed.description or "",
        tuple(
            (field.name, field.value)
            for field in embed.fields
            if field.name != LAST_CHECKED
        ),
        colour,
    )


class Board:
    """Finds, posts and edits the single board message with a given title."""

    def __init__(self, bot, title: str, channel_setting: str):
        self.bot = bot
        self.title = title
        self.channel_setting = channel_setting  # name of the setting holding the channel name
        self._message = None
        self._signature = None
        self._warned_no_channel = False

    def reset(self):
        """Forget the cached message, so the next update looks it up again."""
        self._message = None

    async def drop(self, channel) -> None:
        """Delete the board message, so the next update posts a fresh one below everything else."""
        if self._message is None:
            self._message = await self._find_message(channel)
        if self._message is not None:
            try:
                await self._message.delete()
            except discord.HTTPException:
                pass  # already gone
            self._message = None

    async def _find_message(self, channel):
        async for message in channel.history(limit=50):
            if (
                message.author.id == self.bot.user.id
                and message.embeds
                and message.embeds[0].title == self.title
            ):
                return message
        return None

    def get_channel(self):
        """The board's channel, or None while it is switched off or does not exist."""
        channel_name = getattr(settings, self.channel_setting, "")
        if not channel_name:
            return None
        guild = self.bot.get_guild(int(settings.DISCORD_GUILD_ID))
        channel = (
            discord.utils.get(guild.text_channels, name=channel_name) if guild else None
        )
        if channel is None:
            if not self._warned_no_channel:
                logger.warning(
                    "%s: no text channel named #%s yet", self.title, channel_name
                )
                self._warned_no_channel = True
            return None
        self._warned_no_channel = False
        return channel

    async def update(self, embed) -> None:
        channel = self.get_channel()
        if channel is None:
            return
        channel_name = channel.name

        # Discord draws <t:...:R> as a live "5 minutes ago" and <t:...:t> as the reader's local time
        stamp = int(time.time())
        embed.add_field(
            name=LAST_CHECKED, value=f"<t:{stamp}:R>, at <t:{stamp}:t>", inline=False
        )

        if self._message is None:
            self._message = await self._find_message(channel)
            if self._message is not None:
                self._signature = signature(self._message.embeds[0])
                logger.info("%s: found the board message in #%s", self.title, channel_name)

        if self._message is None:
            self._message = await channel.send(embed=embed)
            self._signature = signature(embed)
            logger.info("%s: board posted in #%s", self.title, channel_name)
            return

        # edited at every check, so the "last checked" time moves even when nothing else changed
        try:
            await self._message.edit(embed=embed)
        except discord.NotFound:
            # somebody deleted the board; post a new one next round
            self._message = None
            return
        if signature(embed) != self._signature:
            self._signature = signature(embed)
            logger.info("%s: board updated in #%s", self.title, channel_name)
