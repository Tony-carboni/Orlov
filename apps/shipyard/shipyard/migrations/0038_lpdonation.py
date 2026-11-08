# Shipyard 0.39.0: donated LP (owner, 2026-11-08).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0037_booksbaseline_carry"),
    ]

    operations = [
        migrations.CreateModel(
            name="LpDonation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("received_at", models.DateTimeField(help_text="When the LP arrived, EVE time (or when you counted them in the wallet); inside the period that is open")),
                ("units", models.PositiveIntegerField(help_text="Loyalty points received")),
                ("donor", models.CharField(blank=True, help_text="Who gave them, for the log", max_length=100)),
                ("note", models.CharField(blank=True, max_length=200)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "LP donation",
                "verbose_name_plural": "LP donations",
                "ordering": ["received_at"],
            },
        ),
    ]
