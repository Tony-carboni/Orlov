from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="shipconfig",
            name="tag_cost_isk",
            field=models.DecimalField(decimal_places=2, default=0, help_text="Other extra inputs per run (ISK), typed by hand", max_digits=15),
        ),
        migrations.AddField(
            model_name="shipconfig",
            name="tag_type_id",
            field=models.PositiveIntegerField(blank=True, help_text="EVE type ID of a tag or other item the LP store offer needs; priced at the market's lowest sell at every refresh", null=True),
        ),
        migrations.AddField(
            model_name="shipconfig",
            name="tag_quantity",
            field=models.PositiveSmallIntegerField(default=1, help_text="How many of that item one copy needs"),
        ),
    ]
