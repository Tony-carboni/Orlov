import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0009_oremarketstats")]

    operations = [
        migrations.CreateModel(
            name="ScrapItem",
            fields=[
                ("type_id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("group", models.CharField(default="Other", help_text="Group shown on the Scrapmetal tab, e.g. 'Smartbombs'", max_length=60)),
                ("group_order", models.PositiveIntegerField(default=999)),
                ("variant", models.CharField(default="other", help_text="Compact | Enduring | Scoped | Restrained | Ample | other, from the name", max_length=12)),
                ("meta_level", models.PositiveSmallIntegerField(default=0)),
                ("portion_size", models.PositiveIntegerField(default=1)),
                ("volume", models.FloatField(default=0, help_text="Packaged m³ per unit")),
                ("materials", models.JSONField(default=dict, help_text="{material type id: quantity per unit before yield}")),
                ("is_active", models.BooleanField(default=True)),
                ("avg_daily_volume", models.FloatField(default=0)),
                ("avg_price", models.FloatField(default=0)),
                ("stats_fetched_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"ordering": ["group_order", "group", "name"]},
        ),
        migrations.AddField(
            model_name="usersettings",
            name="scrapmetal_processing",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
