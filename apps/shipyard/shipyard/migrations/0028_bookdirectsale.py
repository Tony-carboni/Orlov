from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0027_bookignoredentry"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookDirectSale",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("entry_id", models.BigIntegerField()),
                ("items", models.CharField(help_text="Comma-separated, a quantity before each name: '2,388 Zero-Point Condensate, 373 Crystalline Isogen-10'. An ore is converted to its minerals as the ledger does; a name without a quantity takes every unit held", max_length=500)),
                ("note", models.CharField(blank=True, max_length=200)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name": "direct sale", "verbose_name_plural": "direct sales", "unique_together": {("corporation_id", "entry_id")}},
        ),
    ]
