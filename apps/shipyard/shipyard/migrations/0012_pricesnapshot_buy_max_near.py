from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0011_ship_units_per_run")]

    operations = [
        migrations.AddField(
            model_name="pricesnapshot",
            name="buy_max_near",
            field=models.FloatField(help_text="Highest buy order that reaches the station, incl. nearby systems in range (ESI)", null=True),
        ),
    ]
