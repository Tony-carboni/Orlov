# Shipyard 0.31.0: a member's ignored categories and items and flagged items on the Bargains tab.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("shipyard", "0034_markettypestat_vslow"),
    ]

    operations = [
        migrations.CreateModel(
            name="BargainPrefs",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ignored_paths", models.JSONField(blank=True, default=list, help_text="Market-group paths (any level) whose items are hidden")),
                ("ignored_types", models.JSONField(blank=True, default=list, help_text="Type ids hidden")),
                ("starred_types", models.JSONField(blank=True, default=list, help_text="Type ids flagged by the member")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="shipyard_bargain_prefs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "bargain preferences", "verbose_name_plural": "bargain preferences"},
        ),
    ]
