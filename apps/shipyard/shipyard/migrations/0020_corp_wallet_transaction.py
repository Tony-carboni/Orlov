from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0019_wallet_excluded_payer"),
    ]

    operations = [
        migrations.CreateModel(
            name="CorpWalletTransaction",
            fields=[
                ("transaction_id", models.BigIntegerField(primary_key=True, serialize=False)),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("division", models.PositiveSmallIntegerField()),
                ("date", models.DateTimeField(db_index=True)),
                ("type_id", models.PositiveIntegerField(db_index=True)),
                ("quantity", models.BigIntegerField(default=0)),
                ("unit_price", models.FloatField(default=0)),
                ("is_buy", models.BooleanField(default=False)),
                ("client_id", models.BigIntegerField(default=0)),
                ("location_id", models.BigIntegerField(default=0)),
                ("journal_ref_id", models.BigIntegerField(default=0)),
            ],
            options={"ordering": ["-date"]},
        ),
    ]
