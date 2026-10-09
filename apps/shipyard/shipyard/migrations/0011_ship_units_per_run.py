from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0010_scrapitem")]

    operations = [
        migrations.AddField(
            model_name="ship",
            name="units_per_run",
            field=models.PositiveIntegerField(default=1, help_text="Products per blueprint run (40 for fuel blocks)"),
        ),
    ]
