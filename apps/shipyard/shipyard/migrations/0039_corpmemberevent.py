# Shipyard 0.40.0: the Director page, members who left (owner, 2026-11-14).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0038_lpdonation"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="general",
            options={
                "default_permissions": (),
                "managed": False,
                "permissions": (
                    ("basic_access", "Can access the Shipyard dashboard"),
                    ("reprocessing_access", "Can use the Reprocessing tab only (no other Shipyard pages)"),
                    ("dashboard_access", "Can use the ship dashboard and My settings only (no other Shipyard pages)"),
                    ("manage_shipyard", "Can edit blueprint prices, LP prices and facilities"),
                    ("view_corp_industry", "Can see the industry of everyone in their corporation"),
                    ("view_alliance_industry", "Can see the industry of everyone in the alliance"),
                    ("books_access", "Can see the corporation's balance sheet (Finance tab)"),
                    ("refresh_prices", "Can press Refresh on the dashboards (queues the Jita price refreshes, nothing else)"),
                    ("director_access", "Can open the Director page (the corporation's directors)"),
                ),
            },
        ),
        migrations.CreateModel(
            name="CorpMemberEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("notification_id", models.BigIntegerField(help_text="EVE's notification id", unique=True)),
                ("kind", models.CharField(choices=[("left", "left the corporation"), ("applied", "applied"), ("accepted", "application accepted"), ("withdrawn", "withdrew the application"), ("invited", "invited")], db_index=True, max_length=10)),
                ("character_id", models.PositiveIntegerField(db_index=True)),
                ("character_name", models.CharField(blank=True, max_length=100)),
                ("timestamp", models.DateTimeField(db_index=True, help_text="EVE time of the notification")),
                ("text", models.CharField(blank=True, help_text="The application text, for applications", max_length=500)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "corp member event",
                "verbose_name_plural": "corp member events",
                "ordering": ["-timestamp"],
            },
        ),
    ]
