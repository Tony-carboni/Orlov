import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0016_wallet")]

    operations = [
        migrations.CreateModel(
            name="CorpProject",
            fields=[
                ("project_id", models.CharField(max_length=40, primary_key=True, serialize=False)),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("name", models.CharField(max_length=200)),
                ("state", models.CharField(blank=True, max_length=20)),
                ("kind", models.CharField(blank=True, help_text="deliver_item, mine_material, manufacture_item, destroy_ship, manual, …", max_length=40)),
                ("career", models.CharField(blank=True, max_length=30)),
                ("description", models.CharField(blank=True, max_length=1000)),
                ("creator_id", models.BigIntegerField(default=0)),
                ("creator_name", models.CharField(blank=True, max_length=100)),
                ("created", models.DateTimeField(blank=True, null=True)),
                ("expires", models.DateTimeField(blank=True, null=True)),
                ("finished", models.DateTimeField(blank=True, null=True)),
                ("progress_current", models.BigIntegerField(default=0)),
                ("progress_desired", models.BigIntegerField(default=0)),
                ("reward_initial", models.FloatField(default=0)),
                ("reward_remaining", models.FloatField(default=0)),
                ("reward_per_contribution", models.FloatField(default=0)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("last_modified", models.DateTimeField(blank=True, null=True)),
                ("last_seen", models.DateTimeField(default=django.utils.timezone.now)),
                ("missing", models.BooleanField(default=False, help_text="No longer returned by ESI")),
            ],
            options={"ordering": ["-created"]},
        ),
        migrations.CreateModel(
            name="ProjectSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("taken_at", models.DateTimeField(db_index=True)),
                ("state", models.CharField(blank=True, max_length=20)),
                ("progress_current", models.BigIntegerField(default=0)),
                ("reward_remaining", models.FloatField(default=0)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="snapshots", to="shipyard.corpproject")),
            ],
        ),
        migrations.CreateModel(
            name="ProjectContribution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("taken_at", models.DateTimeField(db_index=True)),
                ("character_id", models.BigIntegerField(db_index=True)),
                ("character_name", models.CharField(blank=True, max_length=100)),
                ("contributed", models.BigIntegerField(default=0)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="contributions", to="shipyard.corpproject")),
            ],
        ),
    ]
