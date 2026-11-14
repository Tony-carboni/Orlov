"""Four voice channels: everyone sees who is in them, joining depends on auth (owner's instruction 2026-11-14:
"we want to let people see how active our channels are, without necessarily being able to outright join them").

Runs on the server inside the Discord bot container, through the Django shell, with the bot's token from settings:
    docker compose exec -T allianceauth_discordbot python manage.py shell < voice_channel_visibility.py
Set DRY_RUN = False to make the changes. Only the View Channel and Connect bits of each overwrite change; every
other bit of an existing overwrite stays as it is.

                        unauthed (@everyone)   authed (Family Friend)   member (Family Member)
  voice - public         see + join             see + join               see + join
  Voice - music & relax  see                    see + join               see + join
  voice - Mining         see                    see                      see + join
  voice - PVP            see                    see                      see + join

Roles that already allow Connect on a channel through their own overwrite (Officer, directors) keep it.
"""
import requests
from django.conf import settings

DRY_RUN = True
API = "https://discord.com/api/v10"
FAMILY_MEMBER = "1555294152080498738"
FAMILY_FRIEND_NAME = "Family Friend"
VIEW, CONNECT = 1 << 10, 1 << 20

PLAN = {  # channel name (lower-cased) -> {role key: (view, connect)}
    "voice - public": {"everyone": (True, True), "friend": (True, True), "member": (True, True)},
    "voice - music & relax": {"everyone": (True, False), "friend": (True, True), "member": (True, True)},
    "voice - mining": {"everyone": (True, False), "friend": (True, False), "member": (True, True)},
    "voice - pvp": {"everyone": (True, False), "friend": (True, False), "member": (True, True)},
}

h = {"Authorization": "Bot " + settings.DISCORD_BOT_TOKEN}
g = str(settings.DISCORD_GUILD_ID)
roles = requests.get(f"{API}/guilds/{g}/roles", headers=h, timeout=20).json()
ids = {"everyone": g, "member": FAMILY_MEMBER, "friend": next(r["id"] for r in roles if r["name"] == FAMILY_FRIEND_NAME)}
chs = requests.get(f"{API}/guilds/{g}/channels", headers=h, timeout=20).json()
voice = {c["name"].lower(): c for c in chs if c["type"] == 2}
for name, wanted in PLAN.items():
    c = voice[name]
    current = {o["id"]: o for o in c["permission_overwrites"]}
    print(f"\n#{c['name']} ({c['id']}, parent {c.get('parent_id')})")
    for key, (view, connect) in wanted.items():
        rid = ids[key]
        o = current.get(rid, {"id": rid, "type": 0, "allow": "0", "deny": "0"})
        allow, deny = int(o["allow"]), int(o["deny"])
        for bit, on in ((VIEW, view), (CONNECT, connect)):
            allow, deny = (allow | bit, deny & ~bit) if on else (allow & ~bit, deny | bit)
        changed = (allow, deny) != (int(o["allow"]), int(o["deny"]))
        print(f"  {key:9} view={'yes' if view else 'no ':3} connect={'yes' if connect else 'no ':3} "
              f"allow {int(o['allow'])}->{allow} deny {int(o['deny'])}->{deny} {'CHANGE' if changed else 'as is'}")
        if changed and not DRY_RUN:
            r = requests.put(f"{API}/channels/{c['id']}/permissions/{rid}", headers=h, timeout=20,
                             json={"type": 0, "allow": str(allow), "deny": str(deny)})
            print("   ->", r.status_code)
    others = [o for o in c["permission_overwrites"] if o["id"] not in ids.values()]
    for o in others:
        rname = next((r["name"] for r in roles if r["id"] == o["id"]), o["id"])
        print(f"  other overwrite kept: {rname} allow {o['allow']} deny {o['deny']}")
print("\ndry run" if DRY_RUN else "\ndone")
