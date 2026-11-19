"""Idle moon reminder: a morning note to the directors when one of our refineries has popped
and no new extraction has been set for a day (owner, 2026-11-19: "so I don't forget").

Every morning at ORLOVBOT_MOON_REMINDER_HOUR (EVE time) the bot looks at every refinery that
Moon Mining knows (the corps registered under Moon Mining → Add Owner). A refinery whose last
extraction ended (fractured, auto-fractured or cancelled) more than ORLOVBOT_MOON_REMINDER_IDLE_HOURS
ago, with no extraction started since, is listed in one message in
ORLOVBOT_MOON_REMINDER_CHANNEL. Nothing is posted when every refinery has an extraction running.
The message repeats every morning until a new extraction is set.

- A bot restart after the morning hour posts the day's note once if it was missed (the day is
  remembered in the Django cache).
- /idlemoons runs the same check on request and answers privately (Alliance Director).

docs/runbooks/23-idle-moon-reminder.md
"""

import datetime as dt
import logging

import discord
from asgiref.sync import sync_to_async
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from orlovbot.cogs.structures import _block

logger = logging.getLogger(__name__)

TITLE = "Moons waiting for a new extraction"
CACHE_KEY = "orlovbot:moonreminder:last_day"  # ISO date of the last morning note
ADMIN_ROLE = "Alliance Director"
DEFAULT_HOUR = 8  # EVE time; 09:00 in Brussels in winter


def _hour() -> int:
    return int(getattr(settings, "ORLOVBOT_MOON_REMINDER_HOUR", DEFAULT_HOUR))


def _idle_after() -> dt.timedelta:
    return dt.timedelta(hours=int(getattr(settings, "ORLOVBOT_MOON_REMINDER_IDLE_HOURS", 24)))


def _ago(moment, now) -> str:
    seconds = max(0, int((now - moment).total_seconds()))
    days, rest = divmod(seconds, 86400)
    hours = rest // 3600
    if days:
        return f"{days}d {hours}h ago"
    return f"{hours}h {rest % 3600 // 60}m ago"


def ended_at(extraction):
    """When an extraction stopped being one: fired by hand, cancelled, or auto-fractured."""
    moments = [m for m in (extraction.fractured_at, extraction.canceled_at, extraction.auto_fracture_at) if m]
    return max(moments) if moments else extraction.chunk_arrival_at


def idle_refineries(now) -> list:
    """[{name, moon, ended, last}] for every refinery without a running extraction, idle longer than the threshold."""
    from moonmining.models import Extraction, Refinery

    active = Extraction.Status.considered_active()
    rows = []
    refineries = Refinery.objects.filter(owner__is_enabled=True).select_related("moon__eve_moon").order_by("name")
    for refinery in refineries:
        extractions = refinery.extractions.order_by("-started_at")
        if extractions.filter(status__in=active, canceled_at__isnull=True).exists():
            continue
        last = extractions.first()
        ended = ended_at(last) if last else None
        if ended is not None and (ended > now or now - ended < _idle_after()):
            continue
        rows.append(
            {
                "name": refinery.name,
                "moon": refinery.moon.eve_moon.name if refinery.moon else "unknown moon",
                "ended": ended,
                "last": last,
            }
        )
    return rows


def build_embed(rows: list, now) -> Embed:
    lines = []
    for row in rows:
        ended = row["ended"]
        if ended is None:
            block = [("Popped:", "NO EXTRACTION KNOWN", "red", "Moon Mining has never seen one here")]
        else:
            long_idle = now - ended >= dt.timedelta(days=3)
            block = [("Popped:", _ago(ended, now), "red" if long_idle else "orange", f"{ended:%a %d %b %H:%M} EVE")]
        block.append(("Next:", "NOT SET", "red", "start a new extraction in the Structure Browser"))
        lines.append(f"### {row['name']} ({row['moon']})")
        lines.append(_block(block))
    embed = Embed(title=TITLE, colour=Color.orange())
    embed.description = "\n".join(lines).strip()[:4096]
    embed.set_footer(
        text=f"Idle for more than {int(_idle_after().total_seconds() // 3600)} h. This note repeats every morning at {_hour():02d}:00 EVE until a new extraction runs."
    )
    return embed


async def idle_embed(now):
    """The reminder embed, or None when every refinery has an extraction running."""
    rows = await sync_to_async(idle_refineries)(now)
    if not rows:
        return None
    return build_embed(rows, now)


class MoonReminder(commands.Cog):
    """Morning note about refineries without a new extraction."""

    def __init__(self, bot):
        self.bot = bot
        self._warned_no_channel = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.morning.is_running():
            self.morning.start()
        # a restart after the morning hour must not lose the day's note
        now = timezone.now()
        if now.hour >= _hour() and cache.get(CACHE_KEY) != now.date().isoformat():
            await self.post(now)

    def cog_unload(self):
        self.morning.cancel()

    def get_channel(self):
        name = getattr(settings, "ORLOVBOT_MOON_REMINDER_CHANNEL", "")
        if not name:
            return None
        guild = self.bot.get_guild(int(settings.DISCORD_GUILD_ID))
        channel = discord.utils.get(guild.text_channels, name=name) if guild else None
        if channel is None:
            if not self._warned_no_channel:
                logger.warning("moon reminder: no text channel named #%s", name)
                self._warned_no_channel = True
            return None
        self._warned_no_channel = False
        return channel

    async def post(self, now):
        """One morning note; remembers the day so a reconnect does not repeat it."""
        channel = self.get_channel()
        if channel is None:
            return
        try:
            embed = await idle_embed(now)
        except Exception:
            logger.exception("moon reminder: the check failed")
            return
        cache.set(CACHE_KEY, now.date().isoformat(), timeout=None)
        if embed is None:
            logger.info("moon reminder: every refinery has an extraction running, nothing posted")
            return
        mention = getattr(settings, "ORLOVBOT_MOON_REMINDER_MENTION", "") or ""
        await channel.send(content=mention or None, embed=embed)
        logger.info("moon reminder: posted in #%s", channel.name)

    @tasks.loop(time=dt.time(_hour(), 0, tzinfo=dt.timezone.utc))
    async def morning(self):
        now = timezone.now()
        if cache.get(CACHE_KEY) == now.date().isoformat():
            return
        await self.post(now)

    @commands.slash_command(
        name="idlemoons",
        description="Which of our refineries have no new extraction set (private reply)",
        guild_ids=[int(settings.DISCORD_GUILD_ID)],
    )
    async def idlemoons(self, ctx):
        roles = getattr(ctx.author, "roles", [])
        if not any(role.name == ADMIN_ROLE for role in roles):
            return await ctx.respond(f"This command is for {ADMIN_ROLE}s.", ephemeral=True)
        embed = await idle_embed(timezone.now())
        if embed is None:
            return await ctx.respond("Every refinery has an extraction running.", ephemeral=True)
        return await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(MoonReminder(bot))
