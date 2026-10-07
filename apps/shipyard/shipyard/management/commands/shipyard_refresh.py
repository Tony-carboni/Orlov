"""Run the full data refresh synchronously (no Celery needed)."""

from django.core.management.base import BaseCommand

from ... import tasks


class Command(BaseCommand):
    help = "Refresh indices, builds, prices and market stats now (synchronous)"

    def add_arguments(self, parser):
        parser.add_argument("--prices-only", action="store_true", help="Only prices and market stats")

    def handle(self, *args, **options):
        if not options["prices_only"]:
            self.stdout.write("Facility indices…")
            tasks.refresh_facility_indices()
            self.stdout.write("Builds (EVE Ref, one call per ship per facility)…")
            tasks.refresh_builds()
        self.stdout.write("Prices (Fuzzwork)…")
        tasks.refresh_prices()
        self.stdout.write("Market stats (ESI history)…")
        tasks.refresh_market_stats()
        self.stdout.write(self.style.SUCCESS("Done. Check Shipyard → admin → Refresh runs for errors."))
