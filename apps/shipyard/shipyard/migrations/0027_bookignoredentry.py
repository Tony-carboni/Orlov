# Shipyard 0.21.0: journal lines the Finance tab leaves out.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0026_books_periods"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookIgnoredEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("division", models.PositiveSmallIntegerField()),
                ("entry_id", models.BigIntegerField()),
                ("reason", models.CharField(blank=True, help_text="Why the line is left out", max_length=200)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name": "ignored journal line", "verbose_name_plural": "ignored journal lines", "unique_together": {("corporation_id", "division", "entry_id")}},
        ),
    ]
