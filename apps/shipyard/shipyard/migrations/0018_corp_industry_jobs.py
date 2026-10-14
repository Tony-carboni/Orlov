import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0017_projects")]

    operations = [
        migrations.CreateModel(
            name="CorpIndustryJob",
            fields=[
                ("job_id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("installer_id", models.BigIntegerField(db_index=True, default=0)),
                ("installer_name", models.CharField(blank=True, max_length=100)),
                ("activity_id", models.PositiveSmallIntegerField(default=0)),
                ("blueprint_type_id", models.PositiveIntegerField(default=0)),
                ("product_type_id", models.PositiveIntegerField(blank=True, db_index=True, null=True)),
                ("runs", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(max_length=20)),
                ("start_date", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("end_date", models.DateTimeField(blank=True, null=True)),
                ("completed_date", models.DateTimeField(blank=True, null=True)),
                ("location_id", models.BigIntegerField(default=0)),
                ("cost", models.FloatField(default=0)),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"ordering": ["-start_date"]},
        ),
    ]
