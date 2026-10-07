"""Build the ship catalog from EVE Ref and seed default facility, market and LP factions."""

from django.core.management.base import BaseCommand

from ... import constants
from ...models import Facility, LpFaction, MarketLocation, Ship, ShipConfig
from ...services import catalog


class Command(BaseCommand):
    help = "Load/refresh the T1 + faction hull catalog from EVE Ref and seed defaults"

    def add_arguments(self, parser):
        parser.add_argument("--no-seed", action="store_true", help="Skip seeding facility/market/LP defaults")

    def handle(self, *args, **options):
        if not options["no_seed"]:
            self.seed()
        created, updated = 0, 0
        seen = set()
        for row in catalog.iter_catalog():
            default_active = row.pop("default_active")
            seen.add(row["type_id"])
            ship, was_created = Ship.objects.get_or_create(
                type_id=row["type_id"], defaults={**row, "is_active": default_active}
            )
            if was_created:
                created += 1
            else:
                for k, v in row.items():
                    setattr(ship, k, v)
                ship.save()
                updated += 1
            ShipConfig.objects.get_or_create(ship=ship, defaults=self._default_config(ship))
        self.stdout.write(self.style.SUCCESS(f"Catalog: {created} new, {updated} updated, {len(seen)} total."))
        self.stdout.write("Next: shipyard_refresh (or wait for the beat task).")

    def _default_config(self, ship):
        """Navy ships get their empire LP store pre-linked (LP cost left at 0 to fill in)."""
        store = constants.NAVY_LP_STORE.get(ship.faction_id) if ship.category == constants.CAT_NAVY else None
        faction = LpFaction.objects.filter(name=store).first() if store else None
        return {"lp_faction": faction}

    def seed(self):
        fac, created = Facility.objects.get_or_create(
            name="Orlov Raitaru — Isikano",
            defaults={
                "structure_type_id": 35825,
                "structure_name": "Raitaru",
                "system_id": 30001387,
                "system_name": "Isikano",
                "rig_type_ids": [37154, 37146, 43732],
                "facility_tax": 0,
                "notes": "Corp Raitaru. Basic ME I rigs for small, medium and large ships (check against the actual fit).",
                "is_default": True,
            },
        )
        self.stdout.write(f"Facility '{fac}': {'created' if created else 'exists'}")
        jita, created = MarketLocation.objects.get_or_create(
            name="Jita IV-4 (Caldari Navy Assembly Plant)",
            defaults={
                "station_id": constants.JITA_44_STATION_ID,
                "region_id": constants.THE_FORGE_REGION_ID,
                "is_npc_station": True,
                "sales_tax_base": 7.5,
                "broker_fee_base": 3.0,
                "is_default": True,
            },
        )
        self.stdout.write(f"Market '{jita}': {'created' if created else 'exists'}")
        for name in list(constants.NAVY_LP_STORE.values()) + [
            "Guristas Pirates", "Angel Cartel", "Blood Raider Covenant", "Sansha's Nation", "Serpentis",
            "Mordu's Legion", "Sisters of EVE", "ORE", "Triglavian Collective", "EDENCOM", "Deathless Circle",
        ]:
            LpFaction.objects.get_or_create(name=name)
        self.stdout.write("LP factions seeded (set ISK per LP in Shipyard → Blueprints & LP).")
