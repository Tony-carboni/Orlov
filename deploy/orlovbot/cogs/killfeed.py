"""The kill feed: one post for every ship our pilots kill or lose.

Every 5 minutes the bot asks zKillboard for the latest killmails of our alliance (and of
any extra corps in ORLOVBOT_KILLFEED_CORPORATION_IDS) and posts the ones it has not posted
yet in the channel named by ORLOVBOT_KILLFEED_CHANNEL: green for a kill, red for a loss.
What was posted is remembered in the Django cache (redis), so a bot restart neither repeats
nor floods. docs/runbooks/11-kill-feed.md
"""

import datetime as dt
import logging

import discord
import requests
from asgiref.sync import sync_to_async
from discord import Color, Embed
from discord.ext import commands, tasks

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from orlovbot.board import Board

logger = logging.getLogger(__name__)

FEED_NAME = "Kill feed"
ZKB = "https://zkillboard.com"
ESI = "https://esi.evetech.net/latest"
# zKillboard asks every client to say who it is
HEADERS = {
    "User-Agent": "orlov-auth kill feed (allianceauth-discordbot cog, auth.orlovfamily.space)",
    "Accept-Encoding": "gzip",
}
CHECK_MINUTES = 5
MAX_AGE = dt.timedelta(days=3)  # a killmail that reaches zKillboard later than this is skipped
MAX_POSTS_PER_ROUND = 10  # the rest follows at the next check
MAX_OWN_PILOTS = 5
SEEN_KEY = "orlovbot:killfeed:seen"  # killmail id -> killmail time, kept in the cache
TEST_KEY = "orlovbot:killfeed:test"  # set to make the bot post the newest killmail once more


def _ours() -> tuple:
    alliances = set(getattr(settings, "ORLOVBOT_KILLFEED_ALLIANCE_IDS", []))
    corporations = set(getattr(settings, "ORLOVBOT_KILLFEED_CORPORATION_IDS", []))
    return alliances, corporations


def _when(killmail: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(killmail["killmail_time"].replace("Z", "+00:00"))


def _fetch(kind: str, entity_id: int) -> list:
    response = requests.get(f"{ZKB}/api/{kind}/{entity_id}/", headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"unexpected answer: {str(data)[:100]}")
    return data


def _with_details(killmail: dict) -> dict:
    """zKillboard normally sends the whole killmail; if not, read it from EVE's API."""
    if "victim" in killmail and "attackers" in killmail:
        return killmail
    response = requests.get(
        f"{ESI}/killmails/{killmail['killmail_id']}/{killmail['zkb']['hash']}/",
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return {**response.json(), "zkb": killmail["zkb"]}


def collect(alliances: set, corporations: set) -> tuple:
    """The latest killmails of everything we follow. Returns (killmails, complete)."""
    killmails = {}
    complete = True
    wanted = [("allianceID", entity_id) for entity_id in sorted(alliances)]
    wanted += [("corporationID", entity_id) for entity_id in sorted(corporations)]
    for kind, entity_id in wanted:
        try:
            for killmail in _fetch(kind, entity_id):
                killmails[killmail["killmail_id"]] = _with_details(killmail)
        except Exception as ex:
            logger.warning("Kill feed: zKillboard gave no answer for %s %s: %s", kind, entity_id, ex)
            complete = False
    return list(killmails.values()), complete


def plan(killmails: list, seen, complete: bool, now) -> tuple:
    """Decide what to post. Pure: no Discord, no cache, no HTTP.

    seen maps a killmail id (as text) to its time, or is None on the very first run.
    Returns (to_post, new_seen); new_seen None means: leave the memory as it is.
    """
    recent = [killmail for killmail in killmails if now - _when(killmail) <= MAX_AGE]
    if seen is None:
        if not complete:
            return [], None  # try again next round rather than start from half a list
        # first run: everything that exists already counts as known, nothing is posted
        return [], {str(k["killmail_id"]): k["killmail_time"] for k in recent}

    new = sorted(
        (k for k in recent if str(k["killmail_id"]) not in seen),
        key=lambda k: (k["killmail_time"], k["killmail_id"]),
    )
    to_post = new[:MAX_POSTS_PER_ROUND]
    new_seen = {
        killmail_id: time
        for killmail_id, time in seen.items()
        if now - dt.datetime.fromisoformat(time.replace("Z", "+00:00"))
        <= MAX_AGE + dt.timedelta(days=1)
    }
    for killmail in to_post:
        new_seen[str(killmail["killmail_id"])] = killmail["killmail_time"]
    return to_post, new_seen


def _is_ours(party: dict, alliances: set, corporations: set) -> bool:
    return (
        party.get("alliance_id") in alliances
        or party.get("corporation_id") in corporations
    )


def _names(ids) -> dict:
    """Names for EVE ids (pilots, corps, alliances, ship types, systems, factions)."""
    ids = {int(entity_id) for entity_id in ids if entity_id}
    try:
        from eveuniverse.models import EveEntity

        resolver = EveEntity.objects.bulk_resolve_names(ids)
        return {entity_id: resolver.to_name(entity_id) for entity_id in ids}
    except Exception as ex:
        logger.warning("Kill feed: could not look up names: %s", ex)
        return {}


def _system_text(solar_system_id, names: dict) -> str:
    name = names.get(solar_system_id) or f"system {solar_system_id}"
    try:
        from eveuniverse.models import EveSolarSystem

        system = (
            EveSolarSystem.objects.select_related("eve_constellation__eve_region")
            .filter(id=solar_system_id)
            .first()
        )
        if system:
            security = round(system.security_status, 1)
            return f"**{system.name}** ({security}), {system.eve_constellation.eve_region.name}"
    except Exception:
        pass
    return f"**{name}**"


def _isk(value) -> str:
    value = float(value or 0)
    for size, unit in ((1e9, "billion"), (1e6, "million"), (1e3, "thousand")):
        if value >= size:
            return f"{value / size:,.1f} {unit} ISK"
    return f"{value:,.0f} ISK"


def _who(party: dict, names: dict) -> str:
    """'Name (Corp)' for a pilot, the NPC or structure name for anything else."""
    name = names.get(party.get("character_id"))
    if not name:
        name = (
            names.get(party.get("faction_id"))
            or names.get(party.get("ship_type_id"))
            or names.get(party.get("corporation_id"))
            or "unknown"
        )
        return f"**{name}**"
    corporation = names.get(party.get("corporation_id"))
    alliance = names.get(party.get("alliance_id"))
    group = " / ".join(text for text in (corporation, alliance) if text)
    return f"**{name}** ({group})" if group else f"**{name}**"


def build_embed(killmail: dict, alliances: set, corporations: set, test: bool = False) -> Embed:
    victim = killmail["victim"]
    attackers = killmail["attackers"]
    final_blow = next((a for a in attackers if a.get("final_blow")), attackers[0] if attackers else {})
    own = [a for a in attackers if _is_ours(a, alliances, corporations)]
    is_loss = _is_ours(victim, alliances, corporations)

    ids = [killmail.get("solar_system_id")]
    for party in [victim, final_blow] + own[:MAX_OWN_PILOTS]:
        ids += [party.get(key) for key in ("character_id", "corporation_id", "alliance_id", "faction_id", "ship_type_id")]
    names = _names(ids)

    ship = names.get(victim.get("ship_type_id")) or "ship"
    victim_name = names.get(victim.get("character_id")) or names.get(victim.get("corporation_id")) or "unknown"
    lines = [f"Victim: {_who(victim, names)}"]
    blow_ship = names.get(final_blow.get("ship_type_id"))
    blow = _who(final_blow, names)
    if blow_ship and final_blow.get("character_id"):
        blow += f" in a {blow_ship}"
    lines.append(f"Final blow: {blow}")
    if own:
        pilots = [names.get(a.get("character_id")) or "unknown" for a in own[:MAX_OWN_PILOTS]]
        more = f" and {len(own) - MAX_OWN_PILOTS} more" if len(own) > MAX_OWN_PILOTS else ""
        label = "Friendly fire by" if is_loss else "Our pilots"
        lines.append(f"{label}: {', '.join(pilots)}{more}")
    lines.append(f"Attackers: {len(attackers)}")
    lines.append(f"System: {_system_text(killmail.get('solar_system_id'), names)}")
    lines.append(f"Value: **{_isk(killmail.get('zkb', {}).get('totalValue'))}**")
    stamp = int(_when(killmail).timestamp())
    lines.append(f"Time: <t:{stamp}:f> (<t:{stamp}:R>)")

    embed = Embed(
        title=f"{'Loss' if is_loss else 'Kill'}: {ship} ({victim_name})"[:256],
        url=f"{ZKB}/kill/{killmail['killmail_id']}/",
        colour=Color.red() if is_loss else Color.green(),
        description="\n".join(lines)[:4000],
    )
    if victim.get("ship_type_id"):
        embed.set_thumbnail(
            url=f"https://images.evetech.net/types/{victim['ship_type_id']}/icon?size=128"
        )
    if test:
        embed.set_footer(text="Test post: an existing killmail shown once more as an example")
    return embed


def prepare() -> list:
    """Everything up to the posting, in a thread: HTTP, cache and database.

    Returns (killmail_id, embed) pairs; the id is None for a test post.
    """
    alliances, corporations = _ours()
    if not alliances and not corporations:
        return []
    killmails, complete = collect(alliances, corporations)
    seen = cache.get(SEEN_KEY)
    to_post, new_seen = plan(killmails, seen, complete, timezone.now())
    if new_seen is not None:
        # Remember first, post second: the worst case is one missed killmail, never a repeat.
        cache.set(SEEN_KEY, new_seen, timeout=None)
        if seen is None:
            logger.info(
                "%s: first run, %s existing killmails count as already posted",
                FEED_NAME,
                len(new_seen),
            )
    posts = [(k["killmail_id"], build_embed(k, alliances, corporations)) for k in to_post]
    if cache.get(TEST_KEY):
        cache.delete(TEST_KEY)
        if killmails:
            newest = max(killmails, key=lambda k: k["killmail_id"])
            posts.append((None, build_embed(newest, alliances, corporations, test=True)))
    return posts


def forget(killmail_id: int) -> None:
    """A post failed: drop the killmail from the memory so the next check retries it."""
    seen = cache.get(SEEN_KEY) or {}
    if seen.pop(str(killmail_id), None) is not None:
        cache.set(SEEN_KEY, seen, timeout=None)


class Killfeed(commands.Cog):
    """Kills and losses of our pilots, from zKillboard."""

    def __init__(self, bot):
        self.bot = bot
        # only used to find the channel by name
        self.board = Board(bot, FEED_NAME, "ORLOVBOT_KILLFEED_CHANNEL")

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
            posts = await sync_to_async(prepare)()
            for killmail_id, embed in posts:
                try:
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    logger.exception("%s: killmail %s could not be posted", FEED_NAME, killmail_id)
                    if killmail_id:
                        await sync_to_async(forget)(killmail_id)
                    continue
                logger.info("%s: posted %s (%s)", FEED_NAME, killmail_id or "test", embed.title)
        except Exception:
            # never let one failed round stop the loop
            logger.exception("%s: check failed", FEED_NAME)


def setup(bot):
    bot.add_cog(Killfeed(bot))
