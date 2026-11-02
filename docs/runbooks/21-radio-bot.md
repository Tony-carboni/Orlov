# Runbook 21 — Radio in comms

**Goal (owner, 2026-11-02; options in `docs/research/10-discord-background-music.md`):** background music in the voice channel for quiet moments. The Orlov auth bot joins the caller's voice channel and plays internet radio; every member sets their own level or mutes it for themselves.

**How members use it.** In the music voice channel (Voice1, or any channel with "music" in its name): `/radio on` starts the first station (or `/radio on station:Drone Zone`), `/radio next` switches, `/radio stations` lists them, `/radio off` stops. **Your own level:** right-click the bot in the voice channel → *User Volume*; drag it to zero or tick *Mute* to switch it off for yourself only. The bot's own level (`/radio volume 30`) is a floor under everyone's slider. The bot leaves on its own when the channel empties.

| What | Where |
|---|---|
| Code | `deploy/orlovbot/cogs/radio.py` → `~/aa-docker/orlovbot/cogs/radio.py`; registered in `deploy/orlovbot/auth_hooks.py` |
| Image | `deploy/custom.dockerfile` → `~/aa-docker/custom.dockerfile`: ffmpeg and libopus0 (apt, as root for that layer); `PyNaCl` and `davey==0.1.7` (py-cord's voice extra) in `conf/requirements.txt`. Discord requires its end-to-end voice encryption (DAVE, close code 4017 without it); davey 0.2.0 of 2026-11-02 gave silent audio with py-cord 2.8.1, hence the pin |
| Settings | `ORLOVBOT_RADIO_STATIONS` (name and stream URL each), `ORLOVBOT_RADIO_VOLUME` (0 to 1), `ORLOVBOT_RADIO_CHANNELS` (the radio plays only in voice channels whose name contains one of these words; owner, 2026-11-02: the music channel only, so the bot is not on comms for everyone) in `~/aa-docker/conf/local.py`; template `deploy/conf/local.py.append` |
| Stations | 21 by genre (2026-11-02): Lofi, Lofi Plaza, Chill, Ambient, Space, Deep House, Prog House, Minimal, Dubstep, Soul, 70s, Lounge, Spy Lounge, Jazz, Indie, Rock, Eclectic, Mellow, Metal, 80s, Vaporwave; SomaFM, Nightwave Plaza and Radio Paradise streams, each decode-tested from the container |

## A. Build the image with voice (server — local session)

1. Copy `deploy/custom.dockerfile` to `~/aa-docker/custom.dockerfile` and add `PyNaCl` to `~/aa-docker/conf/requirements.txt`.
2. Backup (`~/bin/aa-backup.sh`), then `docker compose --env-file=.env build` (every service shares the image).
3. Throwaway check in the bot's image: `ffmpeg -version`, `python -c "import nacl"`, `python -c "import discord; discord.opus._load_default(); print(discord.opus.is_loaded())"`.

✅ Done when all three print without error.

## B. Install the cog (server — local session)

1. Copy `deploy/orlovbot/cogs/radio.py` and `deploy/orlovbot/auth_hooks.py` to `~/aa-docker/orlovbot/`.
2. Append the `ORLOVBOT_RADIO_*` settings to `~/aa-docker/conf/local.py`.
3. `docker compose --env-file=.env up -d` (recreates every container on the new image), then read the bot's log: it must list `orlovbot.cogs.radio` among the loaded cogs.

✅ Done when a member in a voice channel runs `/radio on` and hears the station; the bot's status shows "Listening to <station>".

## C. Changing it

- Another station: add a line to `ORLOVBOT_RADIO_STATIONS` and restart the bot. Any direct MP3 or AAC stream URL works; read the station's FAQ on use first.
- Default level: `ORLOVBOT_RADIO_VOLUME`, restart the bot.
- The bot never starts on its own: someone in the channel runs `/radio on`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "/radio on" answers but no sound | The listener's own user volume on the bot may be zero; or ffmpeg is missing (section A step 3). |
| The bot joins and leaves at once | The stream URL is dead; try `/radio next`, then fix the URL in `local.py`. |
| "Join a voice channel first" | The caller is not in a voice channel. |
| The bot stays after everyone left | The empty check runs once a minute; it leaves within a minute. |
