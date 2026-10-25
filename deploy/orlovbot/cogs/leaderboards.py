"""Leaderboards: one board message per leaderboard in the channel named by ORLOVBOT_LEADERBOARD_CHANNEL,
refreshed once a day at ORLOVBOT_LEADERBOARD_HOUR EVE (owner, 2026-10-25; docs/runbooks/20-leaderboards-bot.md).

The first leaderboard: project payouts. The top ORLOVBOT_LEADERBOARD_TOP pilots by ISK earned from the
corporation's projects in the last ORLOVBOT_LEADERBOARD_DAYS days, from the Shipyard plugin's payout events
(a member's deliveries into a project times the project's reward per unit; payouts never touch the corporation
journal). Per pilot: a character registered in Alliance Auth counts for its main character, so adding alts to
auth pools their deliveries; an unregistered character stands on its own name.
"""

import datetime as dt
import logging
from collections import defaultdict

from asgiref.sync import sync_to_async
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings
from django.utils import timezone

from orlovbot.board import Board

logger = logging.getLogger(__name__)

PAYOUTS_TITLE = "Project payouts, top pilots of the last 30 days"


def _settings() -> dict:
    return {
        "days": int(getattr(settings, "ORLOVBOT_LEADERBOARD_DAYS", 30) or 30),
        "top": int(getattr(settings, "ORLOVBOT_LEADERBOARD_TOP", 5) or 5),
        "hour": int(getattr(settings, "ORLOVBOT_LEADERBOARD_HOUR", 14) or 0),
    }


def _mil(isk: float) -> str:
    return f"{isk / 1e6:,.1f} M"


def payout_rows(days: int) -> dict:
    """Synchronous (Django ORM): {rows: [{name, isk, projects, deliveries, registered}], total, members, since, until}.
    Rows per pilot, highest first."""
    from allianceauth.authentication.models import CharacterOwnership
    from shipyard.services import projectbooks

    until = timezone.now()
    since = until - dt.timedelta(days=days)
    events = [e for e in projectbooks.payout_events() if e["t"] >= since]
    ids = {e["member"] for e in events}
    main_of = {}
    for own in CharacterOwnership.objects.filter(character__character_id__in=ids).select_related("character", "user__profile__main_character"):
        main = own.user.profile.main_character
        main_of[own.character.character_id] = (main.character_name if main else own.character.character_name)
    pilots = {}
    for e in events:
        key = main_of.get(e["member"]) or e["name"] or str(e["member"])
        row = pilots.setdefault(key, {"name": key, "isk": 0.0, "projects": set(), "deliveries": 0, "registered": e["member"] in main_of})
        row["isk"] += e["isk"]
        row["projects"].add(e["pid"])
        row["deliveries"] += 1
    rows = sorted(pilots.values(), key=lambda r: -r["isk"])
    for r in rows:
        r["projects"] = len(r["projects"])
    return {"rows": rows, "total": sum(e["isk"] for e in events), "members": len(rows), "since": since, "until": until}


def _name(text: str, width: int) -> str:
    """The pilot's name in bold green, padded to the column (the ANSI codes take no width)."""
    return "\u001b[1;32m" + f"{text:<{width}}" + "\u001b[0m"


def payouts_embed(data: dict, top: int) -> Embed:
    """The board: a ranked table in an ANSI code block in the structure board's colours (owner, 2026-10-25:
    name in bold green, ISK, projects; no deliveries, no runners-up), and the lines of totals."""
    rows = data["rows"][:top]
    embed = Embed(title=PAYOUTS_TITLE, colour=Color.gold())
    if not rows:
        embed.description = "No project payouts in this period yet."
        return embed
    width = max(len(r["name"]) for r in rows)
    lines = ["```ansi"]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. {_name(r['name'], width)}  {_mil(r['isk']):>10}   {r['projects']:>2} projects")
    lines.append("```")
    foot = [f"ISK earned from Orlov Arms International projects, {data['since']:%d %b} to {data['until']:%d %b}. "
            "Thank you for keeping the buyback running ❤️",
            f"{data['members']} pilots were paid {_mil(data['total'])} in total.",
            "*(Alts registered in auth count for their main.)*"]
    embed.description = ("\n".join(lines) + "\n" + "\n".join(foot))[:4096]
    return embed


async def build_embed() -> Embed:
    cfg = _settings()
    data = await sync_to_async(payout_rows)(cfg["days"])
    return payouts_embed(data, cfg["top"])


class Leaderboards(commands.Cog):
    """Leaderboards kept up to date once a day."""

    def __init__(self, bot):
        self.bot = bot
        self.board = Board(bot, PAYOUTS_TITLE, "ORLOVBOT_LEADERBOARD_CHANNEL")
        hour = _settings()["hour"]
        self.daily.change_interval(time=dt.time(hour, 0, tzinfo=dt.timezone.utc))

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.daily.is_running():
            self.daily.start()
        await self.refresh()  # a restart redraws the board, so it is never missing

    def cog_unload(self):
        self.daily.cancel()

    async def refresh(self):
        try:
            await self.board.update(await build_embed())
        except Exception:
            logger.exception("Leaderboard update failed")
            self.board.reset()

    @tasks.loop(time=dt.time(14, 0, tzinfo=dt.timezone.utc))
    async def daily(self):
        await self.refresh()


def setup(bot):
    bot.add_cog(Leaderboards(bot))
