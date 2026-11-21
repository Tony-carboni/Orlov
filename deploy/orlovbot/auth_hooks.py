from allianceauth import hooks


@hooks.register("discord_cogs_hook")
def register_cogs():
    """Tell allianceauth-discordbot which of our command modules to load."""
    return [
        "orlovbot.cogs.moons",
        "orlovbot.cogs.structures",
        "orlovbot.cogs.killfeed",
        "orlovbot.cogs.jfwatch",
        "orlovbot.cogs.juicy",
        "orlovbot.cogs.welcome",
        "orlovbot.cogs.leaderboards",
        "orlovbot.cogs.radio",
        "orlovbot.cogs.fleets",
        "orlovbot.cogs.moonreminder",
        "orlovbot.cogs.leadership",
        "orlovbot.cogs.blacklist",
    ]
