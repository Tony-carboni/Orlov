import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0015_dashboard_access")]

    operations = [
        migrations.CreateModel(
            name="WalletDivision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("corporation_id", models.PositiveIntegerField()),
                ("division", models.PositiveSmallIntegerField()),
                ("name", models.CharField(blank=True, max_length=100)),
                ("balance", models.FloatField(default=0)),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"unique_together": {("corporation_id", "division")}},
        ),
        migrations.CreateModel(
            name="WalletJournalEntry",
            fields=[
                ("entry_id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("division", models.PositiveSmallIntegerField()),
                ("date", models.DateTimeField(db_index=True)),
                ("ref_type", models.CharField(db_index=True, max_length=60)),
                ("amount", models.FloatField(default=0)),
                ("balance", models.FloatField(default=0)),
                ("first_party_id", models.BigIntegerField(db_index=True, default=0)),
                ("first_party_name", models.CharField(blank=True, max_length=100)),
                ("first_party_corp_id", models.BigIntegerField(default=0)),
                ("first_party_corp_name", models.CharField(blank=True, max_length=100)),
                ("second_party_id", models.BigIntegerField(default=0)),
                ("second_party_name", models.CharField(blank=True, max_length=100)),
                ("context_id", models.BigIntegerField(default=0)),
                ("context_id_type", models.CharField(blank=True, max_length=40)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("reason", models.CharField(blank=True, max_length=500)),
                ("tax", models.FloatField(default=0)),
                ("tax_receiver_id", models.BigIntegerField(default=0)),
            ],
            options={"ordering": ["-date"]},
        ),
    ]
