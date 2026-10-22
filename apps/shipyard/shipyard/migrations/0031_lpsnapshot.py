# Shipyard 0.25.0: the LP log.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0030_bookignoredentry_amount"),
    ]

    operations = [
        migrations.CreateModel(
            name="LpSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("character_id", models.PositiveIntegerField(db_index=True)),
                ("character_name", models.CharField(blank=True, max_length=100)),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("corporation_name", models.CharField(blank=True, max_length=100)),
                ("loyalty_points", models.BigIntegerField(help_text="The balance at this reading")),
                ("change", models.BigIntegerField(default=0, help_text="Against the previous reading; 0 on the first reading")),
                ("previous_at", models.DateTimeField(blank=True, help_text="When the previous reading of this pair was taken", null=True)),
                ("is_first", models.BooleanField(default=False)),
                ("taken_at", models.DateTimeField(db_index=True)),
            ],
            options={
                "verbose_name": "LP log reading",
                "verbose_name_plural": "LP log readings",
                "ordering": ["-taken_at"],
                "indexes": [models.Index(fields=["character_id", "corporation_id", "taken_at"], name="shipyard_lp_charact_6b1f2e_idx")],
            },
        ),
    ]
