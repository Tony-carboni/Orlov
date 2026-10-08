import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0008_ore")]

    operations = [
        migrations.CreateModel(
            name="OreMarketStats",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("region_id", models.PositiveIntegerField(default=10000002)),
                ("avg_daily_volume", models.FloatField(default=0)),
                ("avg_price", models.FloatField(default=0)),
                ("days", models.PositiveSmallIntegerField(default=7)),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ore", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="market_stats", to="shipyard.ore")),
            ],
        ),
    ]
