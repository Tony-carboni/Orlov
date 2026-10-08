import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0007_contractprice")]

    operations = [
        migrations.CreateModel(
            name="Ore",
            fields=[
                ("type_id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("group_id", models.PositiveIntegerField()),
                ("group_name", models.CharField(max_length=100)),
                ("kind", models.CharField(help_text="ore | ice | moon | abyssal", max_length=10)),
                ("family", models.CharField(help_text="Base ore this is a variant of, e.g. Gneiss", max_length=100)),
                ("variant", models.CharField(default="base", help_text="base | 0 | II | III | IV | X (grade in the name) | +15 | +100 (moon ore)", max_length=10)),
                ("portion_size", models.PositiveIntegerField(default=1)),
                ("volume", models.FloatField(default=0, help_text="m³ per unit")),
                ("materials", models.JSONField(default=dict, help_text="{material type id: quantity per portion}")),
                ("skill_id", models.PositiveIntegerField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"ordering": ["kind", "family", "variant"]},
        ),
    ]
