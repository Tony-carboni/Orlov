"""Blacklist check: a morning note to the directors when a pilot we removed is back (owner,
2026-11-21: "start a blacklist log; if we accidentally let these pilots back in, flag it to us
in the director chat via the bot; run every morning").

The list is the Markdown table in orlovbot/blacklist.md (next to the cogs folder), one row per
pilot: name, EVE character id, Discord user id when known, the date and the reason. Every morning
at ORLOVBOT_BLACKLIST_HOUR (EVE time) the bot reads the file and looks for each pilot in three
places:
- EVE: the character's corporation (public ESI affiliation) is in the alliance
  (ORLOVBOT_ALLIANCE_ID, the corporations listed by ESI for it);
- auth: the character is registered to a user whose state is in ORLOVBOT_BLACKLIST_STATES
  (Family Member by default: member access);
- Discord: the Discord id from the table, or the Discord link of that auth user, is on the server.
Every hit is reported in one message in ORLOVBOT_BLACKLIST_CHANNEL with a ping; nothing is
posted when nobody is found. The note repeats every morning until the pilot is gone again or
taken off the list. A restart after the morning hour posts the day's note once if it was missed.
/blacklist (Alliance Director) shows the list and runs the check on request, privately.

docs/runbooks/25-blacklist.md
"""

import datetime as dt
import logging
from pathlib import Path

import discord
import requests
from asgiref.sync import sync_to_async
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from orlovbot.cogs.structures import _block

logger = logging.getLogger(__name__)

TITLE = "Blacklisted pilot found"
CACHE_KEY = "orlovbot:blacklist:last_day"  # ISO date of the last morning check that posted or found nothing
ADMIN_ROLE = "Alliance Director"
DEFAULT_HOUR = 8  # EVE time, with the idle moon reminder
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "blacklist.md"
ESI = "https://esi.evetech.net/latest"
UA = "orlovbot blacklist check"
DEFAULT_ALLIANCE = 99015337  # The Orlov Family
DEFAULT_STATES = ["Family Member"]


def _hour() -> int:
    return int(getattr(settings, "ORLOVBOT_BLACKLIST_HOUR", DEFAULT_HOUR))


def _file() -> Path:
    return Path(getattr(settings, "ORLOVBOT_BLACKLIST_FILE", "") or DEFAULT_FILE)


def _alliance_id() -> int:
    return int(getattr(settings, "ORLOVBOT_ALLIANCE_ID", DEFAULT_ALLIANCE))


def _states() -> list:
    return list(getattr(settings, "ORLOVBOT_BLACKLIST_STATES", None) or DEFAULT_STATES)


def read_blacklist(path=None) -> list:
    """The rows of the Markdown table: [{name, character_id, discord_id, removed, reason}]; the header and the rule line are skipped."""
    path = path or _file()
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0].lower() == "pilot" or set(cells[0]) <= set("-: "):
            continue
        rows.append(
            {
                "name": cells[0],
                "character_id": int(cells[1]) if cells[1].isdigit() else None,
                "discord_id": int(cells[2]) if cells[2].isdigit() else None,
                "removed": cells[3],
                "reason": cells[4],
            }
        )
    return rows


def esi_get(path: str):
    r = requests.get(f"{ESI}{path}", params={"datasource": "tranquility"}, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.json()


def esi_post(path: str, payload):
    r = requests.post(f"{ESI}{path}", params={"datasource": "tranquility"}, json=payload, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.json()


def resolve_ids(rows: list) -> None:
    """Fill the character id of rows that only carry a name (ESI name lookup, exact match)."""
    missing = [r["name"] for r in rows if not r["character_id"]]
    if not missing:
        return
    found = {c["name"].lower(): c["id"] for c in esi_post("/universe/ids/", missing).get("characters", [])}
    for r in rows:
        if not r["character_id"]:
            r["character_id"] = found.get(r["name"].lower())


def find_hits(rows: list, member_lookup) -> list:
    """[(row, [where found, ...])] for the rows found somewhere. member_lookup(uid) -> Discord member or None."""
    from allianceauth.authentication.models import CharacterOwnership
    from allianceauth.services.modules.discord.models import DiscordUser

    resolve_ids(rows)
    ids = [r["character_id"] for r in rows if r["character_id"]]
    affiliation = {a["character_id"]: a for a in esi_post("/characters/affiliation/", ids)} if ids else {}
    alliance_corps = set(esi_get(f"/alliances/{_alliance_id()}/corporations/"))
    corp_ids = sorted({a["corporation_id"] for a in affiliation.values()})
    corp_names = {n["id"]: n["name"] for n in esi_post("/universe/names/", corp_ids)} if corp_ids else {}
    hits = []
    for row in rows:
        where = []
        cid = row["character_id"]
        aff = affiliation.get(cid) if cid else None
        if aff and aff["corporation_id"] in alliance_corps:
            where.append(("EVE:", "IN THE ALLIANCE", f"corp {corp_names.get(aff['corporation_id'], aff['corporation_id'])}"))
        discord_ids = {row["discord_id"]} if row["discord_id"] else set()
        own = CharacterOwnership.objects.filter(character__character_id=cid).select_related("user__profile__state").first() if cid else None
        if own:
            state = own.user.profile.state.name
            if state in _states():
                where.append(("Auth:", "MEMBER ACCESS", f"user {own.user.username}, state {state}"))
            link = DiscordUser.objects.filter(user=own.user).first()
            if link:
                discord_ids.add(int(link.uid))
        for uid in sorted(discord_ids):
            member = member_lookup(uid)
            if member is not None:
                where.append(("Discord:", "ON THE SERVER", f"{member.display_name} ({member.name})"))
        if where:
            hits.append((row, where))
    return hits


def build_embed(hits: list, now) -> Embed:
    lines = []
    for row, where in hits:
        block = [(label, value, "red", note) for label, value, note in where]
        block.append(("Listed:", row["removed"], "", row["reason"][:120]))
        lines.append(f"### {row['name']}")
        lines.append(_block(block))
    embed = Embed(title=TITLE, colour=Color.red())
    embed.description = "\n".join(lines).strip()[:4096]
    embed.set_footer(text=f"orlovbot/blacklist.md, checked every morning at {_hour():02d}:00 EVE. Remove the pilot again, or take them off the list.")
    return embed


def list_embed(rows: list) -> Embed:
    embed = Embed(title="Blacklist", colour=Color.dark_grey())
    embed.description = "\n".join(f"- **{r['name']}** ({r['removed']}): {r['reason'][:150]}" for r in rows)[:4096] or "The list is empty."
    return embed


class Blacklist(commands.Cog):
    """Morning check that no removed pilot is back."""

    def __init__(self, bot):
        self.bot = bot
        self._warned_no_channel = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.morning.is_running():
            self.morning.start()
        now = timezone.now()
        if now.hour >= _hour() and cache.get(CACHE_KEY) != now.date().isoformat():
            await self.post(now)

    def cog_unload(self):
        self.morning.cancel()

    def guild(self):
        return self.bot.get_guild(int(settings.DISCORD_GUILD_ID))

    def get_channel(self):
        name = getattr(settings, "ORLOVBOT_BLACKLIST_CHANNEL", "")
        if not name:
            return None
        guild = self.guild()
        channel = discord.utils.get(guild.text_channels, name=name) if guild else None
        if channel is None:
            if not self._warned_no_channel:
                logger.warning("blacklist: no text channel named #%s", name)
                self._warned_no_channel = True
            return None
        self._warned_no_channel = False
        return channel

    async def check(self):
        """(rows, hits) with the Discord lookup against the guild's member cache."""
        guild = self.guild()
        rows = await sync_to_async(read_blacklist)()
        hits = await sync_to_async(find_hits)(rows, lambda uid: guild.get_member(uid) if guild else None)
        return rows, hits

    async def post(self, now):
        channel = self.get_channel()
        if channel is None:
            return
        try:
            rows, hits = await self.check()
        except Exception:
            logger.exception("blacklist: the check failed")
            return
        cache.set(CACHE_KEY, now.date().isoformat(), timeout=None)
        if not hits:
            logger.info("blacklist: %d pilots checked, nobody found", len(rows))
            return
        mention = getattr(settings, "ORLOVBOT_BLACKLIST_MENTION", "") or ""
        await channel.send(content=mention or None, embed=build_embed(hits, now))
        logger.info("blacklist: %d of %d pilots found, posted in #%s", len(hits), len(rows), channel.name)

    @tasks.loop(time=dt.time(_hour(), 0, tzinfo=dt.timezone.utc))
    async def morning(self):
        now = timezone.now()
        if cache.get(CACHE_KEY) == now.date().isoformat():
            return
        await self.post(now)

    @commands.slash_command(
        name="blacklist",
        description="The blacklist, and whether any of them is back (private reply)",
        guild_ids=[int(settings.DISCORD_GUILD_ID)],
    )
    async def blacklist(self, ctx):
        roles = getattr(ctx.author, "roles", [])
        if not any(role.name == ADMIN_ROLE for role in roles):
            return await ctx.respond(f"This command is for {ADMIN_ROLE}s.", ephemeral=True)
        await ctx.defer(ephemeral=True)
        try:
            rows, hits = await self.check()
        except Exception:
            logger.exception("blacklist: the check failed")
            return await ctx.followup.send("The check failed; see the bot log.", ephemeral=True)
        embeds = [list_embed(rows)]
        if hits:
            embeds.append(build_embed(hits, timezone.now()))
        return await ctx.followup.send(content=None if hits else "Nobody on the list was found.", embeds=embeds, ephemeral=True)


def setup(bot):
    bot.add_cog(Blacklist(bot))
