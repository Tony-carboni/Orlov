"""Background music in comms (owner, 2026-11-02; docs/runbooks/21-radio-bot.md, docs/research/10-discord-background-music.md).

The bot joins the caller's voice channel and plays internet radio stations from ORLOVBOT_RADIO_STATIONS, one after
the other on /radio next or when a stream drops. One stream for the whole channel; every listener sets their own
level with Discord's user volume on the bot (right-click the bot in the voice channel), or mutes it for themselves.
The bot's own output level is ORLOVBOT_RADIO_VOLUME (a floor under everyone's slider), changeable with /radio volume.
The bot leaves when the channel empties (checked every minute) or on /radio off.

Needs ffmpeg and libopus in the container (deploy/custom.dockerfile) and PyNaCl (conf/requirements.txt).
"""

import logging

import discord
from discord.ext import commands, tasks

from django.conf import settings

logger = logging.getLogger(__name__)

MEMBER_ROLE = "Family Member"
FFMPEG_BEFORE = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"


def stations() -> list:
    """[{name, url}] from settings; an empty list switches the cog's commands off with a message."""
    return [dict(s) for s in getattr(settings, "ORLOVBOT_RADIO_STATIONS", []) or []]


def default_volume() -> float:
    return max(0.0, min(2.0, float(getattr(settings, "ORLOVBOT_RADIO_VOLUME", 0.3) or 0.3)))


class Radio(commands.Cog):
    """Internet radio in the voice channel, for quiet moments on comms."""

    radio = discord.SlashCommandGroup("radio", "Background music in the voice channel", guild_ids=[int(settings.DISCORD_GUILD_ID)])

    def __init__(self, bot):
        self.bot = bot
        self.index = 0
        self.seq = 0
        self.volume = default_volume()
        self.source = None

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.check_empty.is_running():
            self.check_empty.start()

    def cog_unload(self):
        self.check_empty.cancel()

    # --- helpers --------------------------------------------------------------------------------------------------
    def _guild(self):
        return self.bot.get_guild(int(settings.DISCORD_GUILD_ID))

    def _voice(self):
        guild = self._guild()
        return guild.voice_client if guild else None

    def _allowed(self, ctx) -> bool:
        return any(role.name == MEMBER_ROLE for role in getattr(ctx.author, "roles", []))

    def _play(self, voice, station: dict):
        """Start one station on the connected voice client. Each start gets a sequence number: the previous source's
        `after` callback sees it is superseded and does nothing (without this, stopping the old source to start the
        new one re-triggered the old callback, which started yet another station, in a loop). When a stream ends on
        its own, the next station starts two seconds later."""
        self.seq += 1
        my = self.seq
        voice._radio_wanted = True
        if voice.is_playing() or voice.is_paused():
            voice.stop()
        audio = discord.FFmpegPCMAudio(station["url"], before_options=FFMPEG_BEFORE, options="-vn")
        self.source = discord.PCMVolumeTransformer(audio, volume=self.volume)

        def after(error):
            if error:
                logger.warning("radio: %s stopped: %s", station["name"], error)
            if my != self.seq or not getattr(voice, "_radio_wanted", False) or not voice.is_connected():
                return  # superseded by a newer start, or switched off on purpose
            self.index = (self.index + 1) % max(1, len(stations()))
            nxt = stations()[self.index]
            logger.info("radio: %s ended, next is %s", station["name"], nxt["name"])
            self.bot.loop.call_soon_threadsafe(lambda: self.bot.loop.call_later(2, self._play, voice, nxt))

        voice.play(self.source, after=after)
        self.bot.loop.create_task(self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=station["name"])))
        logger.info("radio: playing %s in #%s", station["name"], voice.channel.name)

    async def _stop(self):
        voice = self._voice()
        if voice is not None:
            voice._radio_wanted = False
            if voice.is_playing():
                voice.stop()
            await voice.disconnect(force=True)
        self.source = None
        await self.bot.change_presence(activity=None)

    # --- commands -------------------------------------------------------------------------------------------------
    @radio.command(name="on", description="Start the radio in your voice channel")
    async def on(self, ctx, station: discord.Option(str, "Station name; the first one when left out", required=False) = None):  # noqa: B008
        if not self._allowed(ctx):
            return await ctx.respond(f"This is for {MEMBER_ROLE}s.", ephemeral=True)
        if not stations():
            return await ctx.respond("No stations are configured (ORLOVBOT_RADIO_STATIONS).", ephemeral=True)
        state = getattr(ctx.author, "voice", None)
        if state is None or state.channel is None:
            return await ctx.respond("Join a voice channel first, then /radio on.", ephemeral=True)
        if station:
            names = [s["name"].lower() for s in stations()]
            if station.lower() not in names:
                return await ctx.respond("Unknown station. " + self._station_list(), ephemeral=True)
            self.index = names.index(station.lower())
        voice = self._voice()
        if voice is None or not voice.is_connected():
            voice = await state.channel.connect()
        elif voice.channel != state.channel:
            await voice.move_to(state.channel)
        self._play(voice, stations()[self.index])
        await ctx.respond(f"Radio on in #{state.channel.name}: {stations()[self.index]['name']}. Set your own level by right-clicking me in the channel.")

    @radio.command(name="off", description="Stop the radio and leave the voice channel")
    async def off(self, ctx):
        if not self._allowed(ctx):
            return await ctx.respond(f"This is for {MEMBER_ROLE}s.", ephemeral=True)
        await self._stop()
        await ctx.respond("Radio off.")

    @radio.command(name="next", description="Switch to the next station")
    async def next(self, ctx):
        if not self._allowed(ctx):
            return await ctx.respond(f"This is for {MEMBER_ROLE}s.", ephemeral=True)
        voice = self._voice()
        if voice is None or not voice.is_connected():
            return await ctx.respond("The radio is off; /radio on first.", ephemeral=True)
        self.index = (self.index + 1) % len(stations())
        self._play(voice, stations()[self.index])
        await ctx.respond(f"Now: {stations()[self.index]['name']}.")

    @radio.command(name="stations", description="List the stations")
    async def list_stations(self, ctx):
        await ctx.respond(self._station_list(), ephemeral=True)

    @radio.command(name="volume", description="The radio's own level, 0 to 100 (everyone still has their own slider)")
    async def set_volume(self, ctx, percent: discord.Option(int, "0 to 100", min_value=0, max_value=100)):  # noqa: B008
        if not self._allowed(ctx):
            return await ctx.respond(f"This is for {MEMBER_ROLE}s.", ephemeral=True)
        self.volume = percent / 100
        if self.source is not None:
            self.source.volume = self.volume
        await ctx.respond(f"Radio level {percent} %.")

    def _station_list(self) -> str:
        return "Stations: " + ", ".join(s["name"] for s in stations()) if stations() else "No stations configured."

    # --- housekeeping ---------------------------------------------------------------------------------------------
    @tasks.loop(minutes=1)
    async def check_empty(self):
        voice = self._voice()
        if voice is None or not voice.is_connected():
            return
        others = [m for m in voice.channel.members if not m.bot]
        if not others:
            logger.info("radio: #%s is empty, leaving", voice.channel.name)
            await self._stop()


def setup(bot):
    bot.add_cog(Radio(bot))
