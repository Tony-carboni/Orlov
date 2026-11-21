"""The leadership board in #leadership-team: who leads the alliance and its corporations.

One message (orlovbot/board.py) that the bot keeps current, redrawn once a day at
ORLOVBOT_LEADERSHIP_HOUR (EVE time) and at every bot start. Two sections (owner, 2026-11-19,
2026-11-21):

- Alliance leadership: everyone who can see the CEO channel (ORLOVBOT_LEADERSHIP_CEO_CHANNEL,
  #corporate-ceos): the holders of ORLOVBOT_LEADERSHIP_LEADER_ROLE (Alliance Director) first as
  "Leader", then the CEOs, then the directors. How the list is made is not stated on the board.
- Per corporation: a block per corporation, the executor corp first. The corporation's CEO per ESI
  (the Discord account that owns the character; when that character is not on Discord, the corp's
  channel members with the CEO role stand in, an alt of theirs runs the corp), then the corp's other
  channel members as Director. The ORLOVBOT_LEADERSHIP_GROUPS_CORP block (OARMI) also carries the
  auth groups of ORLOVBOT_LEADERSHIP_GROUPS: the OARMI Directors and Officers. The corporations are
  the alliance's (ESI) plus any corporation a channel member belongs to, minus
  ORLOVBOT_LEADERSHIP_HIDE_CORPS.

Names are Discord display names ("[OARMI] Tony_Carboni", the nickname auth sets) inside an ansi
code block, each in the colour the member has in the right-hand pane (owner, 2026-11-21: "to find
them back easier"): the colour of their highest coloured role, mapped by hue to the nearest of
Discord's eight text colours. A group member without a Discord link shows as the corp tag plus the
main character, in white.

docs/runbooks/24-oarmi-leadership-board.md
"""

import colorsys
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
LEADER_LABEL = "Leader"
# Discord's ansi palette, bold.
ANSI = {"red": "1;31", "yellow": "1;33", "green": "1;32", "blue": "1;34", "pink": "1;35", "cyan": "1;36", "white": "1;37"}
# hue (degrees) -> the palette colour (owner, 2026-11-21, after trying the alternatives): Alliance Director's raspberry (340°)
# pink, Corp Director's dark orange (24°) red, Officer's amber (37°) the one yellow there is, Family Member's blue (204°) and
# CEO's violet (256°) blue (a code block has no purple; the owner prefers blue over pink for the CEOs)
HUE_BUCKETS = [(30, "red"), (75, "yellow"), (165, "green"), (195, "cyan"), (265, "blue"), (345, "pink"), (360, "red")]
ESC = chr(27)
NL = chr(10)
ESI = "https://esi.evetech.net/latest"
UA = "orlovbot leadership board"
DEFAULT_ALLIANCE = 99015337  # The Orlov Family


def _groups() -> list:
    return list(getattr(settings, "ORLOVBOT_LEADERSHIP_GROUPS", None) or DEFAULT_GROUPS)


def _hour() -> int:
    return int(getattr(settings, "ORLOVBOT_LEADERSHIP_HOUR", DEFAULT_HOUR))


def _prefix() -> str:
    """Before a name that does not come from Discord: the corp tag of the Discord nicknames."""
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_PREFIX", "[OARMI] "))


def _heading() -> str:
    """Markdown in front of each block title: '### ' is one size up from the text, '## ' two (owner: slightly bigger)."""
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_HEADING", "### "))


def _section_heading() -> str:
    """Markdown in front of the two section titles, one size above the block titles."""
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_SECTION_HEADING", "## "))


def _alliance_title() -> str:
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_ALLIANCE_TITLE", "Alliance leadership"))


def _corps_title() -> str:
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_CORPS_TITLE", "Per corporation"))


def _ceo_channel() -> str:
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_CEO_CHANNEL", "corporate-ceos"))


def _leader_role() -> str:
    """The Discord role whose holders head the alliance list as Leader (owner, 2026-11-21: Tony_Carboni on top)."""
    return str(getattr(settings, "ORLOVBOT_LEADERSHIP_LEADER_ROLE", "Alliance Director"))


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


# ---------------------------------------------------------------- colours


def palette_colour(value: int) -> str:
    """The palette colour nearest to a role colour (0xRRGGBB), by hue; no colour (0) or a grey is white."""
    if not value:
        return "white"
    r, g, b = ((value >> 16) & 255) / 255, ((value >> 8) & 255) / 255, (value & 255) / 255
    hue, _, saturation = colorsys.rgb_to_hls(r, g, b)
    if saturation < 0.15:
        return "white"
    degrees = hue * 360
    for upto, name in HUE_BUCKETS:
        if degrees < upto:
            return name
    return "red"


def member_colour(member) -> str:
    """The colour the member has in the member list: their highest coloured role."""
    return palette_colour(member.colour.value) if member is not None else "white"


def _coloured(text: str, colour: str) -> str:
    return f"{ESC}[{ANSI.get(colour, '1;37')}m{text}{ESC}[0m"


def _sort_key(row) -> str:
    """By the part after the corp tag."""
    return row[0].lower().split("] ", 1)[-1]


# ---------------------------------------------------------------- the auth groups (OARMI)


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


def group_rows(guild, sections: list) -> list:
    """[(display name, label, colour)] for the group members: the label is the singular of the group's title."""
    rows = []
    for title, people in sections:
        label = title[:-1] if title.endswith("s") else title
        group = []
        for uid, main in people:
            member = guild.get_member(uid) if (guild and uid) else None
            name = member.display_name if member else f"{_prefix()}{main}"
            group.append((name, label, member_colour(member)))
        rows.extend(sorted(group, key=_sort_key))
    return rows


# ---------------------------------------------------------------- the corporations (CEO channel)


def corporations_for(channel_uids: list) -> list:
    """[{id, name, ticker, ceo: (uid or None, name), others: [uid]}], the executor corp first.

    channel_uids: the Discord ids of the members who can see the CEO channel (bots excluded).
    The corporations are the alliance's plus the corporation of every channel member's main character,
    minus ORLOVBOT_LEADERSHIP_HIDE_CORPS.
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


def corp_blocks(guild, corps: list, groups: list) -> list:
    """[(title, [(display name, label, colour)])] per corporation: the CEO first, the directors, then the group rows.

    The CEO is the account that owns the corporation's CEO character (ESI). When that character is not
    on Discord, the corporation's channel members with the CEO role stand in (an alt of theirs runs the
    corp: NowhereClone for ThatOneClone, owner 2026-11-21); only when there is nobody at all is the
    character named with "not on Discord". Everyone else in the channel is a Director (owner, 2026-11-21).
    groups = [(display name, label, colour)] from the auth groups, merged into the ORLOVBOT_LEADERSHIP_GROUPS_CORP block.
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
        rows = [(m.display_name, "CEO", member_colour(m)) for m in ceos] or [(f"[{corp['ticker']}] {ceo_name}", "CEO, not on Discord", "white")]
        rows.extend(sorted(((m.display_name, "Director", member_colour(m)) for m in others), key=_sort_key))
        if corp["id"] == _groups_corp():
            listed = {name for name, _, _ in rows}
            rows.extend(row for row in groups if row[0] not in listed)
        blocks.append((f"{corp['name']} [{corp['ticker']}]", rows))
    return blocks


def alliance_rows(blocks: list, leaders=()) -> list:
    """The alliance list: the leaders first, then the CEOs, then the directors, each by name.

    leaders: display names of the members holding the leader role; they are labelled Leader here
    whatever their corporation label is (the corp block still shows them as the corp's CEO)."""
    rows = []
    for _, block in blocks:
        for name, label, colour in block:
            if name in leaders:
                rows.append((name, LEADER_LABEL, colour))
            elif label in ("CEO", "Director"):
                rows.append((name, label, colour))
    order = {LEADER_LABEL: 0, "CEO": 1, "Director": 2}
    return sorted(rows, key=lambda r: (order[r[1]], _sort_key(r)))


# ---------------------------------------------------------------- the embed


def code_block(title, rows: list) -> str:
    """A heading line (none when title is None), then one ansi code block: each name in its own colour, the label after it."""
    width = max(len(name) for name, _, _ in rows) if rows else 0
    lines, previous = [], None
    for name, label, colour in rows:
        if previous in ("CEO", "Director") and label not in ("CEO", "Director", LEADER_LABEL):
            lines.append("")  # a blank line between the directors and the officers (owner, 2026-11-21)
        lines.append(_coloured(name.ljust(width), colour) + "  " + label)
        previous = label
    code = "```ansi" + NL + NL.join(lines or ["nobody yet"]) + NL + "```"
    return code if title is None else f"{_heading()}{title}" + NL + code


def build_embed(blocks: list, leaders=()) -> Embed:
    """blocks = [(title, [(display name, label, colour)])], the executor corp first; leaders = the leaders' display names.

    Two sections (owner, 2026-11-21): the alliance leadership on top, then one block per corporation."""
    parts = [f"{_section_heading()}{_alliance_title()}"]
    parts.append(code_block(None, alliance_rows(blocks, leaders)))  # no block title: the section heading says it (owner, 2026-11-21)
    parts.append(f"{_section_heading()}{_corps_title()}")
    parts += [code_block(title, rows) for title, rows in blocks]
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

    def leaders(self, guild) -> set:
        """Display names of the members holding the leader role."""
        role = discord.utils.get(guild.roles, name=_leader_role()) if guild else None
        return {m.display_name for m in role.members if not m.bot} if role else set()

    async def refresh(self):
        try:
            guild = self.bot.get_guild(int(settings.DISCORD_GUILD_ID))
            groups = group_rows(guild, await sync_to_async(members_by_group)())
            corps = await sync_to_async(corporations_for)(self.channel_uids(guild))
            await self.board.update(build_embed(corp_blocks(guild, corps, groups), self.leaders(guild)))
        except Exception:
            logger.exception("Leadership board update failed")
            self.board.reset()

    @tasks.loop(time=dt.time(_hour(), 0, tzinfo=dt.timezone.utc))
    async def daily(self):
        await self.refresh()


def setup(bot):
    bot.add_cog(Leadership(bot))
