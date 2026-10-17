# Doctrines 0.2.1: SRP as a percentage of a ship's cost, per doctrine.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("doctrines", "0002_doctrineship_variant"),
    ]

    operations = [
        migrations.AddField(
            model_name="doctrine",
            name="srp_percent",
            field=models.PositiveSmallIntegerField(default=0, help_text="Ship replacement paid on a loss, as a percentage of the ship's cost (hull, fit, drones, cargo). Shown as a tag on the page and taken off the 'loss if lost' column. 0 = no SRP tag"),
        ),
    ]
