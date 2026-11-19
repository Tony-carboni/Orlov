"""The OARMI leadership board: who the corp's directors and officers are, in #oarmi-leadership-team.

One message (orlovbot/board.py) that the bot keeps current: a section per auth group named in
ORLOVBOT_LEADERSHIP_GROUPS, listing the main character of every member of that group, sorted by
name. Redrawn once a day at ORLOVBOT_LEADERSHIP_HOUR (EVE time) and at every bot start (owner,
2026-11-19: "a message updated once a day: Directors, Officers"). The channel is read-only for
OARMI members; the auth groups are the source, so the Discord roles and this board always agree.

docs/runbooks/24-oarmi-leadership-board.md
"""

import datetime as dt
import logging

from asgiref.sync import sync_to_async
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings

from orlovbot.board import Board

logger = logging.getLogger(__name__)

BOARD_TITLE = "OARMI leadership team"
DEFAULT_GROUPS = [
    {"title": "Directors", "group": "OARMI Director"},
    {"title": "Officers", "group": "OARMI Officer"},
]
DEFAULT_HOUR = 6  # EVE time


def _groups() -> list:
    return list(getattr(settings, "ORLOVBOT_LEADERSHIP_GROUPS", None) or DEFAULT_GROUPS)


def _hour() -> int:
    return int(getattr(settings, "ORLOVBOT_LEADERSHIP_HOUR", DEFAULT_HOUR))


def members_by_group() -> list:
    """[(title, [main character names])] in the configured order; a missing group gives an empty list."""
    from django.contrib.auth.models import Group

    sections = []
    for item in _groups():
        try:
            group = Group.objects.get(name=item["group"])
        except Group.DoesNotExist:
            logger.warning("leadership board: no auth group named %r", item["group"])
            sections.append((item["title"], []))
            continue
        names = []
        for user in group.user_set.filter(is_active=True).select_related("profile__main_character"):
            main = user.profile.main_character
            names.append(main.character_name if main else user.username)
        sections.append((item["title"], sorted(names, key=str.lower)))
    return sections


def build_embed(sections: list) -> Embed:
    lines = []
    for title, names in sections:
        lines.append(f"## {title}")
        lines.extend(names or ["*nobody yet*"])
        lines.append("")
    embed = Embed(title=BOARD_TITLE, colour=Color.blue())
    embed.description = "\n".join(lines).strip()[:4096]
    embed.set_footer(text="From the auth groups; the Discord roles follow them. Redrawn once a day.")
    return embed


class Leadership(commands.Cog):
    """The daily leadership board."""

    def __init__(self, bot):
        self.bot = bot
        self.board = Board(bot, BOARD_TITLE, "ORLOVBOT_LEADERSHIP_CHANNEL")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.daily.is_running():
            self.daily.start()
        await self.refresh()  # a restart redraws the board, so it is never missing

    def cog_unload(self):
        self.daily.cancel()

    async def refresh(self):
        try:
            sections = await sync_to_async(members_by_group)()
            await self.board.update(build_embed(sections))
        except Exception:
            logger.exception("Leadership board update failed")
            self.board.reset()

    @tasks.loop(time=dt.time(_hour(), 0, tzinfo=dt.timezone.utc))
    async def daily(self):
        await self.refresh()


def setup(bot):
    bot.add_cog(Leadership(bot))
