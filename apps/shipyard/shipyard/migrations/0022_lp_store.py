from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0021_corp_journal_entry"),
    ]

    operations = [
        migrations.CreateModel(
            name="LpOffer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("store_corp_id", models.PositiveIntegerField(db_index=True)),
                ("offer_id", models.PositiveIntegerField()),
                ("type_id", models.PositiveIntegerField(db_index=True)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("lp_cost", models.PositiveIntegerField(default=0)),
                ("isk_cost", models.FloatField(default=0)),
                ("ak_cost", models.PositiveIntegerField(default=0)),
                ("required_items", models.JSONField(blank=True, default=list, help_text="[[type id, quantity], ...] handed in with the LP")),
                ("fetched_at", models.DateTimeField()),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["store_corp_id", "offer_id"], "unique_together": {("store_corp_id", "offer_id")}},
        ),
        migrations.CreateModel(
            name="LpTypeMarket",
            fields=[
                ("type_id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("is_blueprint", models.BooleanField(default=False)),
                ("sell_min", models.FloatField(blank=True, null=True)),
                ("sell_volume", models.FloatField(default=0)),
                ("sell_orders", models.PositiveIntegerField(default=0)),
                ("buy_max", models.FloatField(blank=True, null=True)),
                ("avg_daily_volume", models.FloatField(default=0)),
                ("prices_at", models.DateTimeField(blank=True, null=True)),
                ("volume_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]
