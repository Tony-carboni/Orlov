"""The OARMI leadership board: who the corp's directors and officers are, in #oarmi-leadership-team.

One message (orlovbot/board.py) that the bot keeps current: a section per auth group named in
ORLOVBOT_LEADERSHIP_GROUPS, listing the main character of every member of that group, sorted by
name. Redrawn once a day at ORLOVBOT_LEADERSHIP_HOUR (EVE time) and at every bot start (owner,
2026-11-19: "a message updated once a day: Directors, Officers"). The channel is read-only for
OARMI members; the auth groups are the source, so the Discord roles and this board always agree.

Each section is an ansi code block: the heading in the colour those members' names have in the
member list, the names with the corp tag in front, as the Discord nicknames show them (owner,
2026-11-19).

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
# Discord's ansi palette, bold. The OARMI roles carry no colour of their own; in the member list the
# directors show Corp Director's dark orange (nearest: red) and the officers Officer's amber (orange).
ANSI = {"red": "1;31", "orange": "1;33", "yellow": "1;33", "green": "1;32", "blue": "1;34", "pink": "1;35", "cyan": "1;36", "white": "1;37"}
DEFAULT_COLOURS = {"Directors": "red", "Officers": "orange"}
ESC = chr(27)
NL = chr(10)


def _groups() -> list:
    return list(getattr(settings, "ORLOVBOT_LEADERSHIP_GROUPS", None) or DEFAULT_GROUPS)


def _hour() -> int:
    return int(getattr(settings, "ORLOVBOT_LEADERSHIP_HOUR", DEFAULT_HOUR))


def _colours() -> dict:
    return dict(DEFAULT_COLOURS, **(getattr(settings, "ORLOVBOT_LEADERSHIP_COLOURS", None) or {}))


def _prefix() -> str:
    """Put before every name: the corp tag of the Discord nicknames."""
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_PREFIX", "[OARMI] "))


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


def section_block(title: str, names: list) -> str:
    """One ansi code block: the heading in its colour, then the names as the member list shows them."""
    code = ANSI.get(_colours().get(title, ""), "1;37")
    lines = [f"{ESC}[{code}m{title}{ESC}[0m"]
    if names:
        lines.extend(f"{_prefix()}{name}" for name in names)
    else:
        lines.append("nobody yet")
    return "```ansi" + NL + NL.join(lines) + NL + "```"


def build_embed(sections: list) -> Embed:
    blocks = [section_block(title, names) for title, names in sections]
    embed = Embed(title=BOARD_TITLE, colour=Color.blue())
    embed.description = NL.join(blocks).strip()[:4096]
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
