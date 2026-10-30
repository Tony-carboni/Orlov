"""Retire the FC role and open #pings to every Family Member (owner's decision 2026-10-30, for the November
State of the Union: "every member can send pings, the FC role is dissolved").

Runs on the server inside the Discord bot container, through the Django shell, with the bot's token from settings:
    docker compose exec -T allianceauth_discordbot python manage.py shell < retire_fc_role.py
Set DRY_RUN = False to make the changes. What it does, in order:
  1. #pings: the Family Member role gets what the FC role has there (send messages, @everyone, embeds, attachments,
     history, reactions, threads); nothing else on the channel changes.
  2. The FC auth group loses its members and is deleted (auth's Discord sync would otherwise re-create the role).
  3. The Discord role FC is deleted; Discord drops its channel overwrites by itself.
The FCs category (#fc-discussions, #fittings, voice4) keeps Officer, Corp Director and Alliance Director; whether
members get it too is the owner's call and not done here.
"""
import requests
from django.conf import settings
from django.contrib.auth.models import Group

DRY_RUN = True
API = "https://discord.com/api/v10"
FC_ROLE = "1555294425817817099"
FAMILY_MEMBER = "1555294152080498738"

h = {"Authorization": "Bot " + settings.DISCORD_BOT_TOKEN}
g = settings.DISCORD_GUILD_ID
chs = requests.get(f"{API}/guilds/{g}/channels", headers=h, timeout=20).json()
pings = next(c for c in chs if c["name"] == "pings")
fc_on_pings = next(o for o in pings["permission_overwrites"] if o["id"] == FC_ROLE)
print("pings: FC allow", fc_on_pings["allow"], "deny", fc_on_pings["deny"])
if not DRY_RUN:
    r = requests.put(f"{API}/channels/{pings['id']}/permissions/{FAMILY_MEMBER}", headers=h, timeout=20,
                     json={"type": 0, "allow": fc_on_pings["allow"], "deny": "0"})
    print("pings: Family Member now like FC", r.status_code)

grp = Group.objects.filter(name="FC").first()
if grp:
    members = sorted(u.username for u in grp.user_set.all())
    print("auth group FC members:", members)
    if not DRY_RUN:
        grp.user_set.clear()
        grp.delete()
        print("auth group FC deleted")

if not DRY_RUN:
    r = requests.delete(f"{API}/guilds/{g}/roles/{FC_ROLE}", headers=h, timeout=20)
    print("Discord role FC deleted", r.status_code)
print("dry run" if DRY_RUN else "done")
