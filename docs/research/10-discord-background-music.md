# Background music in comms: options (research, 2026-11-02)

**The ask (owner):** a bot that plays a music playlist into the voice channel for quiet moments on comms, joined from streams; every member can switch it off for themselves, or keep it at a low volume while talking to others.

## What Discord already gives us for free

The per-user part needs no bot feature at all. Any member can right-click the bot while it is in the voice channel and set **User Volume** (0 to 200 %) or **Mute** it. That is local to that member: one person mutes the music, the next keeps it at 30 %. Discord also ducks nothing automatically, so "quiet while talking" is the listener's own volume slider. This holds for every option below.

What Discord does not give: a per-member choice of *which* music plays. One bot in one voice channel plays one thing; listeners only choose how loud.

## Where the music comes from

This is the real decision, because it sets the legal and the maintenance risk.

| Source | Fit | Risk |
|---|---|---|
| **Internet radio streams** (SomaFM's Space Station Soma, Drone Zone, Groove Salad; Nightwave Plaza; EVE Radio, the community station) | Best. Endless, curated, no playlist to maintain, "joining streams together" is a station list the bot rotates. | Stations publish listener streams for personal, non-commercial use; a small alliance Discord is within the spirit of that, but it is not an explicit licence. Check each station's FAQ before adding it; SomaFM's is the one to read first. |
| **Local files on the server** (CCP's EVE soundtrack, royalty-free ambient) | Full control, zero outside dependency. | CCP's soundtrack is CCP's: fine for an EVE community in practice, not formally licensed for rebroadcast. Royalty-free ambient packs are clean. Disk and curation effort. |
| **YouTube** | Biggest catalogue. | Google blocks datacenter addresses (our DigitalOcean droplet) with "sign in to confirm you're not a bot"; the big public bots Groovy and Rythm were shut down by YouTube in 2021. Not a foundation to build on. |
| **Spotify** | | No API for streaming audio to bots; Spotify Listen Along needs Nitro and Premium per listener. Out. |

## The three ways to run it

### A. A radio cog on our own bot (recommended)

Our Discord bot already runs 24/7 in the `allianceauth_discordbot` container (py-cord 2.8, cogs under `deploy/orlovbot/cogs/`). Voice playback is part of py-cord; the container only lacks the voice bits: `ffmpeg`, `libopus0` and the `PyNaCl` package (checked 2026-11-02: none present). One `Dockerfile` change and a rebuild adds them.

A `radio` cog would offer: `/radio on` (joins the caller's voice channel and starts the station list), `/radio station <name>`, `/radio next`, `/radio off`, `/radio volume <percent>` for the bot's own output level (a floor under everyone's personal slider), a status line in the bot's presence ("Listening to Space Station Soma"), and auto-leave when the channel empties. Stations and the output level live in `conf/local.py` like the other cogs' settings.

Costs: ffmpeg transcoding one 128 kbps stream to Opus takes a few percent of one core; the droplet has two. Memory is negligible. No new account, no new bot, no vendor.

"Quiet moments": the bot cannot tell silence from talk reliably (py-cord has no dependable speaking events), so the honest design is a manual switch plus Discord's own per-listener volume. Anyone in the channel toggles the bot; each listener sets how loud it is for them.

### B. A public radio bot

Invite a hosted bot such as the "24/7" radio bot or Himal (30,000 stations). Ten minutes to set up, nothing to maintain, and the same per-user volume applies. Downsides: the free tiers limit 24/7 playback or stations, the bot is a third party inside our server with its own data policy, and this category has a history of disappearing overnight (Groovy, Rythm, FredBoat). Fine for a quick trial before building A.

### C. Discord's Watch Together activity

A voice-channel Activity that plays YouTube for those who opt in. Closest to "each user toggles it": members who do not open the activity hear nothing. But it is video in a window, YouTube ads included, and every listener has to join the activity by hand; it does not run on its own in the background. Not what the ask describes.

## Recommendation

Build A, start with two or three radio stations, and keep the volume floor low (around 30 %). It reuses the bot, the container and the settings pattern we have, costs nothing per month, and the per-member control the owner wants is Discord's own user-volume slider, which the member guide should mention. Try B for an evening first if the owner wants to feel the result before any work is done.

Sources looked at: [24/7 radio bot on top.gg](https://top.gg/bot/758796384689192981), [Himal radio bot](https://top.gg/ar/bot/911805837813641227), [a self-hosted radio bot that takes any stream URL](https://github.com/parzival-space/discord-radio-bot), [execaman/Radio, self-hosted](https://github.com/execaman/Radio).
