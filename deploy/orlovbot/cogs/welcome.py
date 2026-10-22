"""Welcome DM: every member who joins the Discord gets a direct message pointing at #how-to-get-roles.

Owner's request, 2026-10-22. The bot (allianceauth-discordbot, Members intent on) hears the join,
sends the member a DM with the channel link, and, when the member's DMs are closed to the server,
posts the same short note in the channel itself with a mention, so nobody is left without the
pointer. Bots are ignored. Settings (conf/local.py):

- ORLOVBOT_WELCOME = True            switches the DM off when False
- ORLOVBOT_WELCOME_CHANNEL_ID        the channel to point at (#how-to-get-roles)

docs/runbooks/19-welcome-dm.md
"""

import logging

import discord
from discord.ext import commands

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL_ID = 1555292924374417471  # #how-to-get-roles


def enabled() -> bool:
    return bool(getattr(settings, "ORLOVBOT_WELCOME", True))


def channel_id() -> int:
    return int(getattr(settings, "ORLOVBOT_WELCOME_CHANNEL_ID", DEFAULT_CHANNEL_ID))


def message(member: discord.Member, link: str) -> str:
    return (
        f"Welcome to **{member.guild.name}**, {member.display_name}!\n\n"
        f"To see more channels you need your roles. Everything you have to do is in one place: {link}\n\n"
        "In short: log in to auth with your EVE character, link your Discord there, and the roles follow by themselves. "
        "Stuck? Ask in that channel and a director will help."
    )


class Welcome(commands.Cog):
    """DMs every new member the link to #how-to-get-roles."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot or not enabled():
            return
        link = f"https://discord.com/channels/{member.guild.id}/{channel_id()}"
        text = message(member, link)
        try:
            await member.send(text)
            logger.info("welcome: DM sent to %s (%s)", member.display_name, member.id)
            return
        except discord.Forbidden:
            logger.info("welcome: %s (%s) does not accept DMs from the server; posting in the channel instead", member.display_name, member.id)
        except discord.HTTPException:
            logger.exception("welcome: DM to %s (%s) failed; posting in the channel instead", member.display_name, member.id)
        channel = member.guild.get_channel(channel_id())
        if channel is None:
            logger.warning("welcome: channel %s not found in %s", channel_id(), member.guild.name)
            return
        try:
            await channel.send(f"{member.mention} welcome! Your DMs are closed, so here it is: the steps to get your roles are at the top of this channel.")
        except discord.HTTPException:
            logger.exception("welcome: channel post for %s failed", member.id)


def setup(bot):
    bot.add_cog(Welcome(bot))
