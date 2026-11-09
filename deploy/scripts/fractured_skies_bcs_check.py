"""Runs on the PC (plain Python, no Django). Read-only: are the four Fractured Skies navy attack battlecruisers
known to ESI and EVE Ref yet, and do the militia LP stores list their blueprint copies?
Usage: python -I deploy/scripts/fractured_skies_bcs_check.py
"""
import json
import urllib.request

ESI = "https://esi.evetech.net/latest"
NAMES = ["Naga Navy Issue", "Oracle Navy Issue", "Talos Navy Issue", "Tornado Fleet Issue"]
MILITIA = {"State Protectorate": 1000180, "24th Imperial Crusade": 1000179, "Federal Defense Union": 1000181, "Tribal Liberation Force": 1000182}


def get(url, data=None):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "orlov-shipyard-check"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


ids = get(f"{ESI}/universe/ids/?datasource=tranquility", json.dumps(NAMES).encode())
types = {t["name"]: t["id"] for t in ids.get("inventory_types", [])}
for n in NAMES:
    tid = types.get(n)
    if not tid:
        print(f"ESI    : {n}: not in ESI yet")
        continue
    ref = ""
    try:
        d = get(f"https://ref-data.everef.net/types/{tid}")
        bps = d.get("produced_by_blueprints") or {}
        ref = f"EVE Ref ok, group {d.get('group_id')}, meta {d.get('meta_group_id')}, faction {d.get('faction_id')}, blueprint(s) {list(bps)}"
    except Exception as exc:  # noqa: BLE001
        ref = f"EVE Ref: {type(exc).__name__} (not synced yet)"
    print(f"ESI    : {n} = {tid}; {ref}")
for store, cid in MILITIA.items():
    try:
        offers = get(f"{ESI}/loyalty/stores/{cid}/offers/?datasource=tranquility")
    except Exception as exc:  # noqa: BLE001
        print(f"LP store {store}: {type(exc).__name__}")
        continue
    hits = [o for o in offers if o["type_id"] in {v + 1 for v in types.values()} or o["type_id"] in types.values() or (o["lp_cost"] == 52000 and int(o["isk_cost"]) == 13_000_000)]
    for o in hits:
        print(f"LP store {store}: type {o['type_id']} x{o['quantity']} for {o['lp_cost']:,} LP + {o['isk_cost']/1e6:.0f} M ISK, requires {o.get('required_items')}")
    if not hits:
        print(f"LP store {store}: no 52,000 LP + 13 M offer yet ({len(offers)} offers)")
