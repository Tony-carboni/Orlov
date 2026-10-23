# Shipyard 0.29.0: the Bargains tab (every type traded in The Forge against its own year).

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0032_hangaritem"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketHistoryDay",
            fields=[
                ("day", models.DateField(primary_key=True, serialize=False)),
                ("total", models.PositiveIntegerField(help_text="Records for the day in EVE Ref's totals.json when fetched; a change means the archive was completed and is fetched again")),
                ("rows", models.PositiveIntegerField(default=0)),
                ("data", models.BinaryField(help_text="zlib-compressed lines: type_id,average,lowest,highest,volume,order_count (The Forge only)")),
                ("fetched_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"verbose_name": "market history day", "verbose_name_plural": "market history days (The Forge)"},
        ),
        migrations.CreateModel(
            name="MarketTypeStat",
            fields=[
                ("type_id", models.PositiveIntegerField(primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, max_length=100)),
                ("market_group_id", models.PositiveIntegerField(blank=True, null=True)),
                ("group_path", models.CharField(blank=True, max_length=300)),
                ("top_group", models.CharField(blank=True, db_index=True, max_length=100)),
                ("as_of", models.DateField(blank=True, null=True)),
                ("last_date", models.DateField(blank=True, null=True)),
                ("last_avg", models.FloatField(blank=True, null=True)),
                ("last_low", models.FloatField(blank=True, null=True)),
                ("low52", models.FloatField(blank=True, null=True)),
                ("low52_date", models.DateField(blank=True, null=True)),
                ("high52", models.FloatField(blank=True, null=True)),
                ("high52_date", models.DateField(blank=True, null=True)),
                ("avg30", models.FloatField(blank=True, null=True)),
                ("avg90", models.FloatField(blank=True, null=True)),
                ("avg365", models.FloatField(blank=True, null=True)),
                ("days365", models.PositiveIntegerField(default=0)),
                ("vol30", models.FloatField(default=0)),
                ("isk30", models.FloatField(db_index=True, default=0)),
                ("sell_min", models.FloatField(blank=True, null=True)),
                ("buy_max", models.FloatField(blank=True, null=True)),
                ("sell_volume", models.FloatField(default=0)),
                ("sell_orders", models.PositiveIntegerField(default=0)),
                ("prices_at", models.DateTimeField(blank=True, null=True)),
                ("pos52", models.FloatField(blank=True, null=True)),
                ("vs90", models.FloatField(blank=True, null=True)),
                ("vs365", models.FloatField(blank=True, null=True)),
                ("flag_low", models.BooleanField(db_index=True, default=False)),
                ("flag_dip", models.BooleanField(db_index=True, default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "market type statistics", "verbose_name_plural": "market type statistics (bargains)"},
        ),
    ]
