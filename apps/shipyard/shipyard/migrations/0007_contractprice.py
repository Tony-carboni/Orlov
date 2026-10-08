import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0006_memberblueprintprice")]

    operations = [
        migrations.CreateModel(
            name="ContractPrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price_per_run", models.DecimalField(decimal_places=2, max_digits=15)),
                ("lowest_per_run", models.DecimalField(decimal_places=2, max_digits=15)),
                ("runs_used", models.PositiveIntegerField(default=0, help_text="Runs that went into the average")),
                ("offers_used", models.PositiveIntegerField(default=0, help_text="Contracts that went into the average")),
                ("contracts", models.PositiveIntegerField(default=0, help_text="Matching contracts in the snapshot")),
                ("runs_available", models.PositiveIntegerField(default=0, help_text="Runs on offer in all matching contracts")),
                ("offers", models.JSONField(blank=True, default=list, help_text="The cheapest contracts: price, runs, ME/TE, station")),
                ("snapshot_at", models.DateTimeField(help_text="EVE Ref scrape time of the snapshot")),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ship", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="contract_price", to="shipyard.ship")),
            ],
        ),
    ]
