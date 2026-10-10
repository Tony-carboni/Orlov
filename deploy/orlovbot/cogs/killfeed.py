"""The kill feed: one post for every ship our pilots kill or lose.

Two sources, one memory:
- **The live feed** (zKillboard's R2Z2, https://zkillboard.com/api/docs/): the bot reads
  the sequence of killmail files as zKillboard writes them, keeps the ones with our pilots
  on either side and posts them within seconds of zKillboard having them.
- **The hourly list** (zKillboard's API, cached by Cloudflare for an hour): every 5 minutes
  the bot asks for the latest killmails of our alliance (and of any extra corps in
  ORLOVBOT_KILLFEED_CORPORATION_IDS) and posts what the stream missed, oldest first.

Posts go to the channel named by ORLOVBOT_KILLFEED_CHANNEL: green for a kill, red for a
loss. What was posted is remembered in the Django cache (redis), so a bot restart neither
repeats nor floods. docs/runbooks/11-kill-feed.md
"""

import asyncio
import datetime as dt
import logging
import time

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

# R2Z2, zKillboard's live feed (https://zkillboard.com/api/docs/, "ephemeral"): every killmail
# zKillboard parses is written as <sequence>.json, sequence numbers strictly increasing; the
# pointer sequence.json names a recent one (refreshed every 51 killmails). A reader fetches
# the files one after the other and waits 6 s after a 404 (= nothing new yet). Files stay
# for 24 h. Every killmail in EVE comes through; we keep the ones with our pilots on them.
# (RedisQ, the earlier stream, was sunset on 2026-05-31; its hostname points at 127.0.0.1.)
R2Z2 = "https://r2z2.zkillboard.com/ephemeral"
STREAM_PAUSE = 1  # seconds between two rounds
STREAM_IDLE_WAIT = 6  # seconds to wait after a 404, as the docs ask
STREAM_STEP_PAUSE = 0.1  # seconds between two files inside a round (the docs' pace; limit 15/s)
STREAM_MAX_PER_ROUND = 50  # files per round, then the memory is saved and Discord gets its turn
STREAM_MAX_BACKLOG = 3000  # further behind than this (about an hour of EVE) → jump to the pointer
STREAM_BACKOFF = 60  # seconds to wait after a failed request
STREAM_LOG_EVERY = dt.timedelta(minutes=15)  # one warning per this while the feed keeps failing
SEQUENCE_KEY = "orlovbot:killfeed:sequence"  # the next sequence number to read, kept in the cache


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


# --- the live feed (R2Z2) ---------------------------------------------------------------

def _stream_enabled() -> bool:
    return bool(getattr(settings, "ORLOVBOT_KILLFEED_STREAM", True))


def fetch_pointer() -> int:
    """The sequence number zKillboard currently points at (a recent one, not the newest)."""
    response = requests.get(f"{R2Z2}/sequence.json", headers=HEADERS, timeout=30)
    response.raise_for_status()
    return int(response.json()["sequence"])


def fetch_sequence(sequence: int) -> dict | None:
    """One killmail file in our usual shape (the ESI killmail plus 'zkb'); None on 404."""
    response = requests.get(f"{R2Z2}/{int(sequence)}.json", headers=HEADERS, timeout=30)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    killmail = data.get("esi") or {}
    if "victim" not in killmail or "attackers" not in killmail:
        raise ValueError(f"sequence {sequence} without a killmail: {str(data)[:100]}")
    return {**killmail, "killmail_id": int(data.get("killmail_id") or killmail.get("killmail_id")), "zkb": data.get("zkb") or {}}


def stream_round(next_sequence: int, alliances: set, corporations: set) -> tuple:
    """Read files from next_sequence on, up to STREAM_MAX_PER_ROUND or the first 404.
    HTTP only, no cache or database. Returns (next sequence to read, our killmails, idle):
    idle is True when the feed has nothing newer yet."""
    ours = []
    for _ in range(STREAM_MAX_PER_ROUND):
        killmail = fetch_sequence(next_sequence)
        if killmail is None:
            return next_sequence, ours, True
        next_sequence += 1
        if involves_us(killmail, alliances, corporations):
            ours.append(killmail)
        time.sleep(STREAM_STEP_PAUSE)
    return next_sequence, ours, False


def involves_us(killmail: dict, alliances: set, corporations: set) -> bool:
    """True when the victim or any attacker is one of ours. Pure."""
    if _is_ours(killmail.get("victim") or {}, alliances, corporations):
        return True
    return any(_is_ours(a, alliances, corporations) for a in killmail.get("attackers") or [])


def plan_stream(killmail: dict, seen, now) -> tuple:
    """Decide whether one stream killmail is posted. Pure.

    Returns (post, new_seen); new_seen None means: leave the memory as it is.
    While seen is None the 5-minute check has not had its first run yet; posting now would
    make that first run post everything older as well, so the stream waits for it.
    """
    if seen is None or now - _when(killmail) > MAX_AGE:
        return False, None
    killmail_id = str(killmail["killmail_id"])
    if killmail_id in seen:
        return False, None
    return True, {**seen, killmail_id: killmail["killmail_time"]}


def prepare_stream(killmail: dict):
    """Memory and embed for one stream killmail, in a thread (cache and database).
    Returns the embed, or None when the killmail is not posted."""
    alliances, corporations = _ours()
    if not involves_us(killmail, alliances, corporations):
        return None
    post, new_seen = plan_stream(killmail, cache.get(SEEN_KEY), timezone.now())
    if not post:
        return None
    cache.set(SEEN_KEY, new_seen, timeout=None)  # remember first, post second
    return build_embed(killmail, alliances, corporations)


class Killfeed(commands.Cog):
    """Kills and losses of our pilots, from zKillboard."""

    def __init__(self, bot):
        self.bot = bot
        # only used to find the channel by name
        self.board = Board(bot, FEED_NAME, "ORLOVBOT_KILLFEED_CHANNEL")
        self.stream_failing_since = None
        self.stream_last_warned = None
        self.rounds = 0

    @commands.Cog.listener()
    async def on_ready(self):
        # on_ready also fires after a reconnect, so only start the loops once
        if not self.check.is_running():
            self.check.start()
        if _stream_enabled() and not self.stream.is_running():
            self.stream.start()

    def cog_unload(self):
        self.check.cancel()
        self.stream.cancel()

    async def _next_sequence(self) -> int:
        """Where to read next: the remembered position, or zKillboard's pointer when there is
        none or the memory is too far behind (a long outage; replaying it all is not worth it)."""
        remembered = await sync_to_async(cache.get)(SEQUENCE_KEY)
        if remembered is None:
            pointer = await sync_to_async(fetch_pointer, thread_sensitive=False)()
            logger.info("%s: live feed starts at sequence %s", FEED_NAME, pointer)
            return pointer
        if self.rounds % 50 == 0:  # about once a minute while idle: compare with the pointer
            pointer = await sync_to_async(fetch_pointer, thread_sensitive=False)()
            if pointer - int(remembered) > STREAM_MAX_BACKLOG:
                logger.warning(
                    "%s: live feed was at sequence %s, zKillboard is at %s; skipping ahead",
                    FEED_NAME, remembered, pointer,
                )
                return pointer
        return int(remembered)

    @tasks.loop(seconds=STREAM_PAUSE)
    async def stream(self):
        """One round of the live feed: read the next files, post the killmails of ours at once."""
        try:
            channel = self.board.get_channel()
            if channel is None:
                await asyncio.sleep(STREAM_BACKOFF)
                return
            self.rounds += 1
            alliances, corporations = _ours()
            # HTTP in a thread of its own: a round may take seconds and must not hold up the
            # database thread the other cogs share
            try:
                next_sequence = await self._next_sequence()
                next_sequence, ours, idle = await sync_to_async(stream_round, thread_sensitive=False)(
                    next_sequence, alliances, corporations
                )
            except Exception as ex:
                self._stream_warn(ex)
                await asyncio.sleep(STREAM_BACKOFF)
                return
            await sync_to_async(cache.set)(SEQUENCE_KEY, next_sequence, None)
            if self.stream_failing_since is not None:
                logger.info("%s: live feed is back", FEED_NAME)
                self.stream_failing_since = self.stream_last_warned = None
            for killmail in ours:
                embed = await sync_to_async(prepare_stream)(killmail)
                if embed is None:
                    continue
                try:
                    await channel.send(embed=embed)
                except discord.HTTPException:
                    logger.exception("%s: killmail %s could not be posted", FEED_NAME, killmail["killmail_id"])
                    await sync_to_async(forget)(killmail["killmail_id"])
                    continue
                logger.info("%s: posted %s from the live feed (%s)", FEED_NAME, killmail["killmail_id"], embed.title)
            if idle:
                await asyncio.sleep(STREAM_IDLE_WAIT)
        except Exception:
            # never let one failed round stop the loop
            logger.exception("%s: live feed round failed", FEED_NAME)
            await asyncio.sleep(STREAM_BACKOFF)

    def _stream_warn(self, ex) -> None:
        """One warning when the feed starts failing, then one every STREAM_LOG_EVERY."""
        now = timezone.now()
        if self.stream_failing_since is None:
            self.stream_failing_since = now
        if self.stream_last_warned is None or now - self.stream_last_warned >= STREAM_LOG_EVERY:
            self.stream_last_warned = now
            logger.warning(
                "%s: live feed gave no answer (since %s): %s; the 5-minute check carries on",
                FEED_NAME, self.stream_failing_since.strftime("%H:%M UTC"), ex,
            )

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
