import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shipyard", "0003_market_owner_and_standings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="general",
            options={
                "default_permissions": (),
                "managed": False,
                "permissions": (
                    ("basic_access", "Can access the Shipyard dashboard"),
                    ("manage_shipyard", "Can edit blueprint prices, LP prices and facilities"),
                    ("view_corp_industry", "Can see the industry of everyone in their corporation"),
                    ("view_alliance_industry", "Can see the industry of everyone in the alliance"),
                ),
            },
        ),
        migrations.CreateModel(
            name="CharacterSync",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("character_id", models.PositiveIntegerField()),
                ("character_name", models.CharField(max_length=100)),
                ("jobs_at", models.DateTimeField(blank=True, null=True)),
                ("blueprints_at", models.DateTimeField(blank=True, null=True)),
                ("assets_at", models.DateTimeField(blank=True, null=True)),
                ("manufacturing_slots", models.PositiveSmallIntegerField(default=1)),
                ("science_slots", models.PositiveSmallIntegerField(default=1)),
                ("last_error", models.CharField(blank=True, max_length=300)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shipyard_characters", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("user", "character_id")}},
        ),
        migrations.CreateModel(
            name="IndustryJob",
            fields=[
                ("job_id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("character_id", models.PositiveIntegerField()),
                ("character_name", models.CharField(max_length=100)),
                ("activity_id", models.PositiveSmallIntegerField(default=0)),
                ("blueprint_type_id", models.PositiveIntegerField(default=0)),
                ("product_type_id", models.PositiveIntegerField(blank=True, null=True)),
                ("runs", models.PositiveIntegerField(default=0)),
                ("licensed_runs", models.IntegerField(blank=True, null=True)),
                ("status", models.CharField(max_length=20)),
                ("start_date", models.DateTimeField(blank=True, null=True)),
                ("end_date", models.DateTimeField(blank=True, null=True)),
                ("location_id", models.BigIntegerField(default=0)),
                ("cost", models.FloatField(default=0)),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shipyard_jobs", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="CharacterBlueprint",
            fields=[
                ("item_id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("character_id", models.PositiveIntegerField()),
                ("type_id", models.PositiveIntegerField()),
                ("location_id", models.BigIntegerField(default=0)),
                ("location_flag", models.CharField(blank=True, max_length=50)),
                ("me", models.PositiveSmallIntegerField(default=0)),
                ("te", models.PositiveSmallIntegerField(default=0)),
                ("runs", models.IntegerField(default=-1)),
                ("quantity", models.IntegerField(default=-1, help_text="-1 original, -2 copy, >0 a stack of originals")),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shipyard_blueprints", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="CharacterAsset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("character_id", models.PositiveIntegerField()),
                ("type_id", models.PositiveIntegerField()),
                ("location_id", models.BigIntegerField(default=0)),
                ("quantity", models.BigIntegerField(default=0)),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shipyard_assets", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("user", "character_id", "type_id", "location_id")}},
        ),
        migrations.CreateModel(
            name="LocationName",
            fields=[
                ("location_id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200)),
                ("system_name", models.CharField(blank=True, max_length=100)),
                ("kind", models.CharField(default="unknown", max_length=20)),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
    ]
