"""The leadership board in #leadership-team: who leads the alliance and its corporations.

One message (orlovbot/board.py) that the bot keeps current, redrawn once a day at
ORLOVBOT_LEADERSHIP_HOUR (EVE time) and at every bot start. Two sections (owner, 2026-11-19,
2026-11-21):

- Alliance leadership: everyone who can see the CEO channel (ORLOVBOT_LEADERSHIP_CEO_CHANNEL,
  #corporate-ceos), CEOs first, then directors. How the list is made is not stated on the board.
- Per corporation: a block per corporation, the executor corp first. The corporation's CEO per ESI
  (the Discord account that owns the character; when that character is not on Discord, the corp's
  channel members with the CEO role stand in, an alt of theirs runs the corp), then the corp's other
  channel members as Director. The ORLOVBOT_LEADERSHIP_GROUPS_CORP block (OARMI) also carries the
  auth groups of ORLOVBOT_LEADERSHIP_GROUPS: the OARMI Directors and Officers. The corporations are
  the alliance's (ESI) plus any corporation a channel member belongs to, minus
  ORLOVBOT_LEADERSHIP_HIDE_CORPS.

Names are Discord display names ("[OARMI] Tony_Carboni", the nickname auth sets) in the colour of
their label inside an ansi code block: CEO pink, Director red, Officer orange. A group member
without a Discord link shows as the corp tag plus the main character.

docs/runbooks/24-oarmi-leadership-board.md
"""

import datetime as dt
import logging

import discord
import requests
from asgiref.sync import sync_to_async
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings

from orlovbot.board import Board

logger = logging.getLogger(__name__)

BOARD_TITLE = "Leadership team"
DEFAULT_GROUPS = [
    {"title": "Directors", "group": "OARMI Director"},
    {"title": "Officers", "group": "OARMI Officer"},
]
DEFAULT_HOUR = 6  # EVE time
# Discord's ansi palette, bold. The OARMI roles carry no colour of their own; in the member list the
# directors show Corp Director's dark orange (nearest: red) and the officers Officer's amber (orange).
# CEO's violet is nearest to pink.
ANSI = {"red": "1;31", "orange": "1;33", "yellow": "1;33", "green": "1;32", "blue": "1;34", "pink": "1;35", "cyan": "1;36", "white": "1;37"}
DEFAULT_COLOURS = {"Directors": "red", "Officers": "orange", "CEO": "pink", "Director": "red", "Officer": "orange", "Member": "white"}
DIRECTOR_ROLES = ("Corp Director", "OARMI Director", "Alliance Director")
ESC = chr(27)
NL = chr(10)
ESI = "https://esi.evetech.net/latest"
UA = "orlovbot leadership board"
DEFAULT_ALLIANCE = 99015337  # The Orlov Family


def _groups() -> list:
    return list(getattr(settings, "ORLOVBOT_LEADERSHIP_GROUPS", None) or DEFAULT_GROUPS)


def _hour() -> int:
    return int(getattr(settings, "ORLOVBOT_LEADERSHIP_HOUR", DEFAULT_HOUR))


def _colours() -> dict:
    return dict(DEFAULT_COLOURS, **(getattr(settings, "ORLOVBOT_LEADERSHIP_COLOURS", None) or {}))


def _prefix() -> str:
    """Before a name that does not come from Discord: the corp tag of the Discord nicknames."""
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_PREFIX", "[OARMI] "))


def _heading() -> str:
    """Markdown in front of each block title: '### ' is one size up from the text, '## ' two (owner: slightly bigger)."""
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_HEADING", "### "))


def _section_heading() -> str:
    """Markdown in front of the two section titles, one size above the block titles."""
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_SECTION_HEADING", "## "))


def _oarmi_title() -> str:
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_OARMI_TITLE", "OARMI leadership"))


def _alliance_title() -> str:
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_ALLIANCE_TITLE", "Alliance leadership"))


def _corps_title() -> str:
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_CORPS_TITLE", "Per corporation"))


def _ceo_channel() -> str:
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_CEO_CHANNEL", "corporate-ceos"))


def _groups_corp() -> int:
    """The corporation whose block carries the auth groups (Directors, Officers): OARMI."""
    return int(getattr(settings, "ORLOVBOT_LEADERSHIP_GROUPS_CORP", 98843356))


def _hidden_corps() -> set:
    """Corporation ids left off the board (owner, 2026-11-21: W T I, about to disband, no attention wanted)."""
    return {int(c) for c in (getattr(settings, "ORLOVBOT_LEADERSHIP_HIDE_CORPS", None) or [])}


def _alliance_id() -> int:
    return int(getattr(settings, "ORLOVBOT_ALLIANCE_ID", DEFAULT_ALLIANCE))


def esi_get(path: str):
    r = requests.get(f"{ESI}{path}", params={"datasource": "tranquility"}, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.json()


def esi_post(path: str, payload):
    r = requests.post(f"{ESI}{path}", params={"datasource": "tranquility"}, json=payload, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- OARMI leadership (auth groups)


def members_by_group() -> list:
    """[(title, [(discord uid or None, main character name)])] in the configured order; a missing group gives an empty list."""
    from django.contrib.auth.models import Group

    from allianceauth.services.modules.discord.models import DiscordUser

    sections = []
    for item in _groups():
        try:
            group = Group.objects.get(name=item["group"])
        except Group.DoesNotExist:
            logger.warning("leadership board: no auth group named %r", item["group"])
            sections.append((item["title"], []))
            continue
        people = []
        for user in group.user_set.filter(is_active=True).select_related("profile__main_character"):
            main = user.profile.main_character
            link = DiscordUser.objects.filter(user=user).first()
            people.append((int(link.uid) if link else None, main.character_name if main else user.username))
        sections.append((item["title"], people))
    return sections


def display_names(guild, people: list) -> list:
    """The Discord display name of each person (the nickname auth sets), else the corp tag and the main character; sorted."""
    names = []
    for uid, main in people:
        member = guild.get_member(uid) if (guild and uid) else None
        names.append(member.display_name if member else f"{_prefix()}{main}")
    return sorted(names, key=lambda n: n.lower().split("] ", 1)[-1])


# ---------------------------------------------------------------- Alliance leadership (CEO channel)


def corporations_for(channel_uids: list) -> list:
    """[{id, name, ticker, ceo: (uid or None, name, on_discord), others: [(uid, is_director)]}], the executor corp first.

    channel_uids: the Discord ids of the members who can see the CEO channel (bots excluded).
    The corporations are the alliance's plus the corporation of every channel member's main character.
    """
    from allianceauth.authentication.models import CharacterOwnership
    from allianceauth.services.modules.discord.models import DiscordUser

    alliance = esi_get(f"/alliances/{_alliance_id()}/")
    corp_ids = set(esi_get(f"/alliances/{_alliance_id()}/corporations/"))
    by_corp = {}  # corp id -> [uid]
    for link in DiscordUser.objects.filter(uid__in=channel_uids).select_related("user__profile__main_character"):
        main = link.user.profile.main_character
        if main is None:
            continue
        corp_ids.add(main.corporation_id)
        by_corp.setdefault(main.corporation_id, []).append(int(link.uid))
    corps = []
    for corp_id in corp_ids - _hidden_corps():
        info = esi_get(f"/corporations/{corp_id}/")
        ceo_id = info["ceo_id"]
        own = CharacterOwnership.objects.filter(character__character_id=ceo_id).select_related("user", "character").first()
        ceo_link = DiscordUser.objects.filter(user=own.user).first() if own else None
        ceo_name = own.character.character_name if own else esi_post("/universe/names/", [ceo_id])[0]["name"]
        ceo_uid = int(ceo_link.uid) if ceo_link else None
        others = [uid for uid in by_corp.get(corp_id, []) if uid != ceo_uid]
        corps.append({"id": corp_id, "name": info["name"], "ticker": info["ticker"], "ceo": (ceo_uid, ceo_name), "others": others})
    executor = alliance.get("executor_corporation_id")
    corps.sort(key=lambda c: (c["id"] != executor, c["name"].lower()))
    return corps


def alliance_blocks(guild, corps: list, group_sections=None) -> list:
    """[(title, [(display name, label)])] per corporation, the CEO first, then the others by name;
    group_sections = [(title, [display names])] from the auth groups, merged into the ORLOVBOT_LEADERSHIP_GROUPS_CORP block.

    The CEO is the account that owns the corporation's CEO character (ESI). When that character is not
    on Discord, the corporation's channel members with the CEO role stand in (an alt of theirs runs the
    corp: NowhereClone for ThatOneClone, owner 2026-11-21); only when there is nobody at all is the
    character named with "not on Discord". Everyone else in the channel is a Director (owner, 2026-11-21:
    the channel is the leadership, so a member there without the CEO seat is a director).
    """
    blocks = []
    for corp in corps:
        ceo_uid, ceo_name = corp["ceo"]
        ceo_member = guild.get_member(ceo_uid) if (guild and ceo_uid) else None
        others = [m for m in (guild.get_member(uid) for uid in corp["others"]) if m is not None] if guild else []
        if ceo_member is not None:
            ceos = [ceo_member]
        else:
            ceos = [m for m in others if any(role.name == "CEO" for role in m.roles)]
            others = [m for m in others if m not in ceos]
        rows = [(m.display_name, "CEO") for m in ceos] or [(f"[{corp['ticker']}] {ceo_name}", "CEO, not on Discord")]
        rows.extend(sorted(((m.display_name, "Director") for m in others), key=lambda r: r[0].lower().split("] ", 1)[-1]))
        if corp["id"] == _groups_corp():
            # the auth groups (Directors, Officers) live in this corporation's block, after the CEO and the channel's directors
            listed = {name for name, _ in rows}
            for title, names in group_sections or []:
                label = title[:-1] if title.endswith("s") else title
                rows.extend((name, label) for name in names if name not in listed)
        blocks.append((f"{corp['name']} [{corp['ticker']}]", rows))
    return blocks


# ---------------------------------------------------------------- the embed


def _coloured(name: str, colour: str) -> str:
    return f"{ESC}[{ANSI.get(colour, '1;37')}m{name}{ESC}[0m"


def section_block(title: str, names: list) -> str:
    """A heading line, then one ansi code block with the names in the section's colour."""
    lines = [_coloured(name, _colours().get(title, "")) for name in names] or ["nobody yet"]
    return f"{_heading()}{title}" + NL + "```ansi" + NL + NL.join(lines) + NL + "```"


def corp_block(title, rows: list) -> str:
    """A heading line (none when title is None), then one ansi code block: the name in the colour of its label, the label after it."""
    colours = _colours()
    width = max(len(name) for name, _ in rows) if rows else 0
    lines = []
    for name, label in rows:
        colour = colours.get(label.split(",")[0].split(" (")[0], "white")
        lines.append(_coloured(name.ljust(width), colour) + "  " + label)
    code = "```ansi" + NL + NL.join(lines or ["nobody yet"]) + NL + "```"
    return code if title is None else f"{_heading()}{title}" + NL + code


def everyone_rows(corp_sections: list) -> list:
    """All the channel members in one list, the CEOs first, then by name (the corp tag is in the nickname)."""
    rows = [row for _, block in corp_sections for row in block if row[1] in ("CEO", "Director")]
    return sorted(rows, key=lambda r: (not r[1].startswith("CEO"), r[0].lower().split("] ", 1)[-1]))


def build_embed(corp_sections: list) -> Embed:
    """corp_sections = [(title, [(display name, label)])], the executor corp first.

    Two sections (owner, 2026-11-21): the alliance leadership on top, then one block per corporation."""
    parts = [f"{_section_heading()}{_alliance_title()}"]
    parts.append(corp_block(None, everyone_rows(corp_sections)))  # no block title: the section heading says it (owner, 2026-11-21)
    parts.append(f"{_section_heading()}{_corps_title()}")
    parts += [corp_block(title, rows) for title, rows in corp_sections]
    embed = Embed(title=BOARD_TITLE, colour=Color.blue())
    embed.description = NL.join(parts).strip()[:4096]
    embed.set_footer(text="Redrawn once a day.")
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

    def channel_uids(self, guild) -> list:
        """The Discord ids of the people (no bots) who can see the CEO channel."""
        channel = discord.utils.get(guild.text_channels, name=_ceo_channel()) if guild else None
        if channel is None:
            logger.warning("leadership board: no text channel named #%s", _ceo_channel())
            return []
        return [m.id for m in channel.members if not m.bot]

    async def refresh(self):
        try:
            guild = self.bot.get_guild(int(settings.DISCORD_GUILD_ID))
            raw = await sync_to_async(members_by_group)()
            group_sections = [(title, display_names(guild, people)) for title, people in raw]
            corps = await sync_to_async(corporations_for)(self.channel_uids(guild))
            await self.board.update(build_embed(alliance_blocks(guild, corps, group_sections)))
        except Exception:
            logger.exception("Leadership board update failed")
            self.board.reset()

    @tasks.loop(time=dt.time(_hour(), 0, tzinfo=dt.timezone.utc))
    async def daily(self):
        await self.refresh()


def setup(bot):
    bot.add_cog(Leadership(bot))
