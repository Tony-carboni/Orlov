"""The jump freighter watch: every jump freighter lost in highsec or lowsec, EVE-wide.

Two things live in the channel named by ORLOVBOT_JFWATCH_CHANNEL:
- a post for each new loss that zKillboard registers (blue = highsec, orange = lowsec);
- a summary, "Jump freighter losses", that the bot keeps as the last message of the
  channel: counts for 24 hours, 7 days and 30 days, per day, by hull, by system and by
  who got the final blow.
Nullsec and wormhole losses are left out (ORLOVBOT_JFWATCH_SPACE). One request to
zKillboard every 5 minutes returns the last 200 losses, about two months, which is
enough for all of it. docs/runbooks/12-jf-watch.md
"""

import collections
import datetime as dt
import logging

import discord
from asgiref.sync import sync_to_async
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from orlovbot.board import Board
from orlovbot.cogs import killfeed as kf

logger = logging.getLogger(__name__)

BOARD_TITLE = "Jump freighter losses"
JF_GROUP_ID = 902  # EVE's ship group "Jump Freighter": Anshar, Ark, Nomad, Rhea
CHECK_MINUTES = 5
SEEN_KEY = "orlovbot:jfwatch:seen"  # killmail id -> killmail time, kept in the cache
TEST_KEY = "orlovbot:jfwatch:test"  # set to make the bot post the newest loss once more
SPACE_LABELS = {  # zKillboard's own tag on every killmail
    "loc:highsec": "highsec",
    "loc:lowsec": "lowsec",
    "loc:nullsec": "nullsec",
    "loc:w-space": "wormhole",
}
SPACE_COLOURS = {"highsec": Color.blue(), "lowsec": Color.orange()}
SPARKS = "▁▂▃▄▅▆▇█"
TOP = 5


def _wanted_space() -> list:
    return list(getattr(settings, "ORLOVBOT_JFWATCH_SPACE", ["highsec", "lowsec"]))


def _space(killmail: dict) -> str:
    for label in killmail.get("zkb", {}).get("labels") or []:
        if label in SPACE_LABELS:
            return SPACE_LABELS[label]
    try:  # no tag: work it out from the solar system
        from eveuniverse.models import EveSolarSystem

        system = EveSolarSystem.objects.get(id=killmail["solar_system_id"])
        if system.is_w_space:
            return "wormhole"
        if system.is_high_sec:
            return "highsec"
        if system.is_low_sec:
            return "lowsec"
        return "nullsec"
    except Exception:
        return "unknown"


def collect() -> list:
    """The latest jump freighter losses in the space we watch, newest first."""
    wanted = set(_wanted_space())
    losses = []
    for killmail in kf._fetch("losses/groupID", JF_GROUP_ID):
        space = _space(killmail)
        if space in wanted:
            losses.append({**kf._with_details(killmail), "space": space})
    return losses


def _killer(killmail: dict):
    """Who gets the credit: the alliance (else corp) of the final blow."""
    attackers = killmail["attackers"]
    blow = next((a for a in attackers if a.get("final_blow")), attackers[0] if attackers else {})
    return blow.get("alliance_id") or blow.get("corporation_id") or blow.get("faction_id")


def build_loss_embed(killmail: dict, test: bool = False) -> Embed:
    victim = killmail["victim"]
    attackers = killmail["attackers"]
    final_blow = next((a for a in attackers if a.get("final_blow")), attackers[0] if attackers else {})
    groups = collections.Counter(
        a.get("alliance_id") or a.get("corporation_id")
        for a in attackers
        if a.get("alliance_id") or a.get("corporation_id")
    )
    biggest = groups.most_common(1)

    ids = [killmail.get("solar_system_id")] + [group for group, _ in biggest]
    for party in (victim, final_blow):
        ids += [party.get(key) for key in ("character_id", "corporation_id", "alliance_id", "faction_id", "ship_type_id")]
    names = kf._names(ids)

    ship = names.get(victim.get("ship_type_id")) or "Jump freighter"
    system = names.get(killmail.get("solar_system_id")) or "unknown system"
    lines = [f"Victim: {kf._who(victim, names)}"]
    blow = kf._who(final_blow, names)
    blow_ship = names.get(final_blow.get("ship_type_id"))
    if blow_ship and final_blow.get("character_id"):
        blow += f" in a {blow_ship}"
    lines.append(f"Final blow: {blow}")
    count = f"Attackers: {len(attackers)}"
    if biggest and len(attackers) > 1:
        group, pilots = biggest[0]
        count += f", {pilots} of them from **{names.get(group) or 'unknown'}**"
    lines.append(count)
    lines.append(f"System: {kf._system_text(killmail.get('solar_system_id'), names)}")
    lines.append(f"Value: **{kf._isk(killmail.get('zkb', {}).get('totalValue'))}**")
    stamp = int(kf._when(killmail).timestamp())
    lines.append(f"Time: <t:{stamp}:f> (<t:{stamp}:R>)")

    embed = Embed(
        title=f"{ship} lost in {system} ({killmail['space']})"[:256],
        url=f"{kf.ZKB}/kill/{killmail['killmail_id']}/",
        colour=SPACE_COLOURS.get(killmail["space"], Color.dark_grey()),
        description="\n".join(lines)[:4000],
    )
    if victim.get("ship_type_id"):
        embed.set_thumbnail(
            url=f"https://images.evetech.net/types/{victim['ship_type_id']}/icon?size=128"
        )
    if test:
        embed.set_footer(text="Test post: an existing killmail shown once more as an example")
    return embed


def _tally(losses: list) -> str:
    """'14 (9 highsec, 5 lowsec), 120.1 billion ISK'"""
    spaces = collections.Counter(loss["space"] for loss in losses)
    split = ", ".join(f"{spaces[space]} {space}" for space in _wanted_space() if spaces[space])
    value = sum(float(loss.get("zkb", {}).get("totalValue") or 0) for loss in losses)
    text = f"**{len(losses)}**"
    if losses:
        text += f" ({split}), {kf._isk(value)}"
    return text


def _ranking(counter, names: dict) -> str:
    rows = [f"{names.get(key) or 'unknown'} {count}" for key, count in counter.most_common(TOP)]
    return ", ".join(rows) if rows else "none"


def build_summary(losses: list, now) -> Embed:
    """The trend board. Works on what zKillboard returned: the newest 200 losses."""

    def within(start_days, end_days=0):
        return [
            loss
            for loss in losses
            if dt.timedelta(days=end_days) <= now - kf._when(loss) < dt.timedelta(days=start_days)
        ]

    month = within(30)
    hulls = collections.Counter(loss["victim"].get("ship_type_id") for loss in month)
    systems = collections.Counter(loss.get("solar_system_id") for loss in month)
    killers = collections.Counter(k for k in (_killer(loss) for loss in month) if k)
    top_ids = [key for counter in (hulls, systems, killers) for key, _ in counter.most_common(TOP)]
    newest = losses[0] if losses else None
    if newest:
        top_ids += [newest["victim"].get("ship_type_id"), newest.get("solar_system_id")]
    names = kf._names(top_ids)

    today = now.date()
    per_day = collections.Counter(kf._when(loss).date() for loss in within(14))
    days = [per_day[today - dt.timedelta(days=back)] for back in range(13, -1, -1)]
    top = max(days) or 1
    sparks = "".join(SPARKS[round(count / top * (len(SPARKS) - 1))] for count in days)

    watched = " and ".join(_wanted_space())
    lines = [
        f"Jump freighters lost in **{watched}**, all of EVE, as registered on zKillboard.",
        "",
        f"Last 24 hours: {_tally(within(1))}",
        f"Last 7 days: {_tally(within(7))}",
        f"The 7 days before: **{len(within(14, 7))}**",
        f"Last 30 days: {_tally(month)}",
        f"Per day, last 14 days: `{sparks}` (oldest left, today right; busiest day {max(days)})",
        "",
        f"By hull (30 days): {_ranking(hulls, names)}",
        f"Systems (30 days): {_ranking(systems, names)}",
        f"Final blows (30 days): {_ranking(killers, names)}",
    ]
    if newest:
        ship = names.get(newest["victim"].get("ship_type_id")) or "Jump freighter"
        system = names.get(newest.get("solar_system_id")) or "unknown system"
        stamp = int(kf._when(newest).timestamp())
        lines += [
            "",
            f"Latest: [{ship} in {system}]({kf.ZKB}/kill/{newest['killmail_id']}/) <t:{stamp}:R>",
        ]
    return Embed(title=BOARD_TITLE, colour=Color.blurple(), description="\n".join(lines)[:4096])


def prepare() -> tuple:
    """Everything up to the posting, in a thread. Returns (posts, summary embed).

    posts are (killmail_id, embed) pairs; the id is None for a test post. The summary is
    None when zKillboard did not answer: the round is skipped and the board left as it is.
    """
    try:
        losses = collect()
    except Exception as ex:
        logger.warning("%s: zKillboard gave no answer: %s", BOARD_TITLE, ex)
        return [], None
    now = timezone.now()
    seen = cache.get(SEEN_KEY)
    to_post, new_seen = kf.plan(losses, seen, True, now)
    if new_seen is not None:
        # Remember first, post second: the worst case is one missed loss, never a repeat.
        cache.set(SEEN_KEY, new_seen, timeout=None)
        if seen is None:
            logger.info(
                "%s: first run, %s recent losses count as already posted", BOARD_TITLE, len(new_seen)
            )
    posts = [(loss["killmail_id"], build_loss_embed(loss)) for loss in to_post]
    if cache.get(TEST_KEY):
        cache.delete(TEST_KEY)
        if losses:
            posts.append((None, build_loss_embed(losses[0], test=True)))
    return posts, build_summary(losses, now)


def forget(killmail_id: int) -> None:
    """A post failed: drop the loss from the memory so the next check retries it."""
    seen = cache.get(SEEN_KEY) or {}
    if seen.pop(str(killmail_id), None) is not None:
        cache.set(SEEN_KEY, seen, timeout=None)


class JumpFreighterWatch(commands.Cog):
    """Jump freighter losses in highsec and lowsec, from zKillboard."""

    def __init__(self, bot):
        self.bot = bot
        self.board = Board(bot, BOARD_TITLE, "ORLOVBOT_JFWATCH_CHANNEL")

    @commands.Cog.listener()
    async def on_ready(self):
        # on_ready also fires after a reconnect, so only start the loop once
        if not self.check.is_running():
            self.check.start()

    def cog_unload(self):
        self.check.cancel()

    @tasks.loop(minutes=CHECK_MINUTES)
    async def check(self):
        try:
            # no channel yet: do nothing at all, so the first real run starts clean
            channel = self.board.get_channel()
            if channel is None:
                return
            posts, summary = await sync_to_async(prepare)()
            if summary is None:
                return
            posted = False
            for killmail_id, embed in posts:
                try:
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    logger.exception("%s: loss %s could not be posted", BOARD_TITLE, killmail_id)
                    if killmail_id:
                        await sync_to_async(forget)(killmail_id)
                    continue
                posted = True
                logger.info("%s: posted %s (%s)", BOARD_TITLE, killmail_id or "test", embed.title)
            if posted:
                # the summary goes below the new posts, so it is always the last message
                await self.board.drop(channel)
            await self.board.update(summary)
        except Exception:
            # never let one failed round stop the loop
            logger.exception("%s: check failed", BOARD_TITLE)
            self.board.reset()


def setup(bot):
    bot.add_cog(JumpFreighterWatch(bot))
