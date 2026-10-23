# Shipyard 0.30.0: range filters on the Bargains tab need "vs low" as a column.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0033_bargains"),
    ]

    operations = [
        migrations.AddField(
            model_name="markettypestat",
            name="vslow",
            field=models.FloatField(blank=True, help_text="Today's sell above the 52-week low, as a fraction (0.30.0)", null=True),
        ),
    ]
