import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0018_corp_industry_jobs")]

    operations = [
        migrations.CreateModel(
            name="WalletExcludedPayer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("party_id", models.BigIntegerField()),
                ("party_name", models.CharField(blank=True, max_length=100)),
                ("note", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_by", models.CharField(blank=True, max_length=150)),
            ],
            options={"unique_together": {("corporation_id", "party_id")}},
        ),
    ]
