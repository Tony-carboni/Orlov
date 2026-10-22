"""Juicy killmails: the expensive and the rare losses of all EVE, posted to #juicy-killmails.

The kill feed's live reader (cogs/killfeed.py, zKillboard's R2Z2 files) hands every killmail
in EVE to the bot as the event ``zkill_killmail``. This cog judges each one by the owner's
rules (2026-10-22) and posts the ones that qualify, with the reason in the footer:

- a supercarrier or a titan, whatever the value;
- an alliance tournament or other limited edition ship (the special edition market group,
  without the giveaway hulls such as the Gnosis), whatever the value;
- a faction hull (navy, pirate, CONCORD and the like; meta group 4) above 20 B;
- a jump freighter above 15 B;
- a freighter, Bowhead, Orca or Porpoise above 8 B;
- a hauler (T1 hauler, blockade runner, deep space transport) above 10 B;
- a black ops above 12 B;
- any other non-capital ship above 10 B (black ops and the Marshal have their own rules;
  carriers, dreadnoughts, force auxiliaries, Rorquals and lancers only count as faction
  hulls above 20 B).

The value is zKillboard's total value of the loss. What was posted is remembered in the
Django cache (redis), so a bot restart neither repeats nor floods. The ship's group and
meta group come from ESI (cached a week). docs/runbooks/18-juicy-killmails.md
"""

import logging

import discord
import requests
from asgiref.sync import sync_to_async
from discord import Color, Embed
from discord.ext import commands

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from orlovbot.board import Board
from orlovbot.cogs import killfeed as kf

logger = logging.getLogger(__name__)

FEED_NAME = "Juicy killmails"
SEEN_KEY = "orlovbot:juicy:seen"  # killmail id -> killmail time, kept in the cache
TEST_KEY = "orlovbot:juicy:test"  # set to a killmail id to post that one once more, as a test
TYPE_KEY = "orlovbot:juicy:type:{}"  # ship type -> (name, group id, meta group id)
TYPE_TTL = 7 * 24 * 3600
B = 1_000_000_000

# EVE's ship groups
TITAN, SUPERCARRIER = 30, 659
CARRIER, DREADNOUGHT, FORCE_AUXILIARY, CAPITAL_INDUSTRIAL, LANCER = 547, 485, 1538, 883, 4594
FREIGHTER, JUMP_FREIGHTER, INDUSTRIAL_COMMAND = 513, 902, 941
HAULER, BLOCKADE_RUNNER, DEEP_SPACE_TRANSPORT = 28, 1202, 380
BLACK_OPS = 898
CAPITALS = {TITAN, SUPERCARRIER, CARRIER, DREADNOUGHT, FORCE_AUXILIARY, CAPITAL_INDUSTRIAL, LANCER, FREIGHTER, JUMP_FREIGHTER}
MARSHAL = 44996
META_FACTION = 4  # dogma attribute 1692 (metaGroupID): 1 T1, 2 T2, 4 faction, 14 T3

# The special edition market group (1612) as of 2026-10-22, without the hulls anyone can get
# for nothing (Gnosis, Praxis, Sunesis, Metamorphosis, the shuttles and corvettes, the Quafe
# Miasmos editions, the YC128 campaign buses, Primae, the event destroyers and battlecruiser)
# and without the CONCORD ships (Marshal, Pacifier, Enforcer: faction hulls, the 20 B rule).
LIMITED = {
    # alliance tournament prizes
    32788: "Cambion", 32207: "Freki", 74141: "Geri", 3516: "Malice", 78414: "Shapash", 2834: "Utu",
    85236: "Python", 42246: "Caedes", 33397: "Chremoas", 48636: "Hydra", 85062: "Sidewinder", 45530: "Virtuoso",
    60765: "Raiju", 2836: "Adrestia", 74316: "Bestla", 77726: "Cybele", 32209: "Mimir", 3518: "Vangel",
    35781: "Fiend", 60764: "Laelaps", 35779: "Imp", 33673: "Whiptail", 32790: "Etana", 42245: "Rabisu",
    33675: "Chameleon", 85229: "Cobra", 33395: "Moracha", 48635: "Tiamat", 45531: "Victor",
    # collectors' hulls
    11936: "Apocalypse Imperial Issue", 11938: "Armageddon Imperial Issue", 13202: "Megathron Federate Issue",
    26840: "Raven State Issue", 26842: "Tempest Tribal Issue", 4005: "Scorpion Ishukone Watch",
    11940: "Gold Magnate", 11942: "Silver Magnate", 11011: "Guardian-Vexor", 635: "Opux Luxury Yacht",
}


def _threshold(name: str, default_b: float) -> float:
    return float(getattr(settings, name, default_b)) * B


def ship_info(type_id: int) -> tuple:
    """(name, group id, meta group id) of a ship type, from ESI, cached a week. HTTP only."""
    key = TYPE_KEY.format(int(type_id))
    cached = cache.get(key)
    if cached:
        return tuple(cached)
    response = requests.get(f"{kf.ESI}/universe/types/{int(type_id)}/", headers=kf.HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()
    meta = next((int(a["value"]) for a in data.get("dogma_attributes") or [] if a.get("attribute_id") == 1692), 0)
    info = (data.get("name") or f"Type {type_id}", int(data.get("group_id") or 0), meta)
    cache.set(key, info, TYPE_TTL)
    return info


def judge(value: float, type_id: int, group_id: int, meta: int) -> str | None:
    """The reason a loss is juicy, or None. Pure."""
    extra = set(getattr(settings, "ORLOVBOT_JUICY_EXTRA_TYPE_IDS", []) or [])
    if group_id == TITAN:
        return "Titan"
    if group_id == SUPERCARRIER:
        return "Supercarrier"
    if type_id in LIMITED or type_id in extra:
        return "Limited edition ship"
    if meta == META_FACTION or type_id == MARSHAL:
        return "Faction ship above 20 B" if value >= _threshold("ORLOVBOT_JUICY_FACTION_B", 20) else None
    if group_id == JUMP_FREIGHTER:
        return "Jump freighter above 15 B" if value >= _threshold("ORLOVBOT_JUICY_JUMP_FREIGHTER_B", 15) else None
    if group_id in (FREIGHTER, INDUSTRIAL_COMMAND):
        return "Freighter or Orca above 8 B" if value >= _threshold("ORLOVBOT_JUICY_FREIGHTER_B", 8) else None
    if group_id in (HAULER, BLOCKADE_RUNNER, DEEP_SPACE_TRANSPORT):
        return "Hauler above 10 B" if value >= _threshold("ORLOVBOT_JUICY_HAULER_B", 10) else None
    if group_id == BLACK_OPS:
        return "Black ops above 12 B" if value >= _threshold("ORLOVBOT_JUICY_BLACK_OPS_B", 12) else None
    if group_id in CAPITALS:
        return None
    return "Ship above 10 B" if value >= _threshold("ORLOVBOT_JUICY_SHIP_B", 10) else None


def assess(killmail: dict) -> str | None:
    """The reason for one killmail, with the ship looked up. HTTP and cache, no database."""
    type_id = int((killmail.get("victim") or {}).get("ship_type_id") or 0)
    if not type_id:
        return None
    value = float((killmail.get("zkb") or {}).get("totalValue") or 0)
    _, group_id, meta = ship_info(type_id)
    return judge(value, type_id, group_id, meta)


def build_embed(killmail: dict, reason: str, test: bool = False) -> Embed:
    victim = killmail["victim"]
    attackers = killmail.get("attackers") or []
    final_blow = next((a for a in attackers if a.get("final_blow")), attackers[0] if attackers else {})
    ids = [killmail.get("solar_system_id")]
    for party in (victim, final_blow):
        ids += [party.get(key) for key in ("character_id", "corporation_id", "alliance_id", "faction_id", "ship_type_id")]
    names = kf._names(ids)
    ship = names.get(victim.get("ship_type_id")) or ship_info(victim["ship_type_id"])[0]
    system = names.get(killmail.get("solar_system_id")) or "unknown system"
    lines = [f"Victim: {kf._who(victim, names)}"]
    blow = kf._who(final_blow, names)
    blow_ship = names.get(final_blow.get("ship_type_id"))
    if blow_ship and final_blow.get("character_id"):
        blow += f" in a {blow_ship}"
    lines.append(f"Final blow: {blow}")
    lines.append(f"Attackers: {len(attackers)}")
    lines.append(f"System: {kf._system_text(killmail.get('solar_system_id'), names)}")
    lines.append(f"Value: **{kf._isk(killmail.get('zkb', {}).get('totalValue'))}**")
    stamp = int(kf._when(killmail).timestamp())
    lines.append(f"Time: <t:{stamp}:f> (<t:{stamp}:R>)")
    embed = Embed(
        title=f"{ship} lost in {system}"[:256],
        url=f"{kf.ZKB}/kill/{killmail['killmail_id']}/",
        colour=Color.gold(),
        description="\n".join(lines)[:4000],
    )
    if victim.get("ship_type_id"):
        embed.set_thumbnail(url=f"https://images.evetech.net/types/{victim['ship_type_id']}/render?size=128")
    embed.set_footer(text=f"{reason}" + (" · test post: shown once more as an example" if test else ""))
    return embed


def prepare(killmail: dict):
    """Judge, remember, build: in a thread. Returns the embed, or None when the loss is not posted."""
    reason = assess(killmail)
    if reason is None:
        return None
    now = timezone.now()
    if now - kf._when(killmail) > kf.MAX_AGE:
        return None
    seen = cache.get(SEEN_KEY) or {}
    killmail_id = str(killmail["killmail_id"])
    if killmail_id in seen:
        return None
    seen = {k: v for k, v in seen.items() if now - kf._when({"killmail_time": v}) <= kf.MAX_AGE}
    seen[killmail_id] = killmail["killmail_time"]
    cache.set(SEEN_KEY, seen, timeout=None)  # remember first, post second
    return build_embed(killmail, reason)


def forget(killmail_id: int) -> None:
    seen = cache.get(SEEN_KEY) or {}
    if seen.pop(str(killmail_id), None) is not None:
        cache.set(SEEN_KEY, seen, timeout=None)


def fetch_killmail(killmail_id: int) -> dict | None:
    """One killmail by id from zKillboard, in the usual shape (for a test post)."""
    rows = requests.get(f"{kf.ZKB}/api/killID/{int(killmail_id)}/", headers=kf.HEADERS, timeout=30).json()
    if not rows:
        return None
    return kf._with_details(rows[0])


def prepare_test():
    """A test post asked for through the cache: TEST_KEY holds a killmail id."""
    killmail_id = cache.get(TEST_KEY)
    if not killmail_id:
        return None
    cache.delete(TEST_KEY)
    killmail = fetch_killmail(killmail_id)
    if killmail is None:
        return None
    reason = assess(killmail) or "Test post (would not qualify)"
    return build_embed(killmail, reason, test=True)


class JuicyKillmails(commands.Cog):
    """The expensive and rare losses of all EVE, from the kill feed's live reader."""

    def __init__(self, bot):
        self.bot = bot
        self.board = Board(bot, FEED_NAME, "ORLOVBOT_JUICY_CHANNEL")

    @commands.Cog.listener()
    async def on_zkill_killmail(self, killmail: dict):
        try:
            channel = self.board.get_channel()
            if channel is None:
                return
            embed = await sync_to_async(prepare, thread_sensitive=False)(killmail)
            if embed is None:
                return
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                logger.exception("%s: killmail %s could not be posted", FEED_NAME, killmail["killmail_id"])
                await sync_to_async(forget, thread_sensitive=False)(killmail["killmail_id"])
                return
            logger.info("%s: posted %s (%s; %s)", FEED_NAME, killmail["killmail_id"], embed.title, embed.footer.text)
        except Exception:
            logger.exception("%s: killmail %s failed", FEED_NAME, killmail.get("killmail_id"))

    @commands.Cog.listener()
    async def on_zkill_idle(self):
        """The live reader has nothing new: a moment for a test post, if one was asked for."""
        try:
            channel = self.board.get_channel()
            if channel is None:
                return
            embed = await sync_to_async(prepare_test, thread_sensitive=False)()
            if embed is not None:
                await channel.send(embed=embed)
                logger.info("%s: test post (%s)", FEED_NAME, embed.title)
        except Exception:
            logger.exception("%s: test post failed", FEED_NAME)


def setup(bot):
    bot.add_cog(JuicyKillmails(bot))
