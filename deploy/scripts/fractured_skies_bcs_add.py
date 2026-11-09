"""Runs in the Django shell on the server, after `shipyard_load_ships` has pulled the four Fractured Skies navy attack
battlecruisers from EVE Ref. Fills in the LP store offer on each (expansion notes of 2026-11-06: blueprint copies for
52,000 LP and 13 million ISK in the four militia stores; runs per copy assumed 1 like the other navy battlecruisers,
check the LP conversion tab). Idempotent: rows that already carry an LP cost are left alone.
"""
from shipyard.models import Ship, ShipConfig

OFFERS = {
    "Naga Navy Issue": "Caldari Navy",
    "Oracle Navy Issue": "Imperial Navy",
    "Talos Navy Issue": "Federation Navy",
    "Tornado Fleet Issue": "Republic Fleet",
}
LP, ISK = 52_000, 13_000_000
for name, faction_name in OFFERS.items():
    ship = Ship.objects.filter(name=name).first()
    if ship is None:
        print("OUT", name, ": not in the catalog yet (run shipyard_load_ships first)")
        continue
    cfg, _ = ShipConfig.objects.get_or_create(ship=ship)
    if cfg.lp_cost:
        print("OUT", name, ": already configured", cfg.lp_faction, cfg.lp_cost, cfg.lp_isk_cost, cfg.lp_runs)
        continue
    from shipyard.models import LpFaction
    cfg.lp_faction = LpFaction.objects.filter(name=faction_name).first()
    cfg.lp_cost, cfg.lp_isk_cost, cfg.lp_runs = LP, ISK, 1
    cfg.notes = "Militia LP store: 52,000 LP + 13 M ISK, no tag (Fractured Skies, 2026-11-10)"
    cfg.save()
    print("OUT", name, f"({ship.type_id}, blueprint {ship.blueprint_type_id}, category {ship.category}, active {ship.is_active}) -> {faction_name}, {LP:,} LP + {ISK/1e6:.0f} M, 1 run")
