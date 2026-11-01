from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shipyard", "0036_refresh_prices"),
    ]

    operations = [
        migrations.AddField(
            model_name="booksbaseline",
            name="carry",
            field=models.FloatField(default=0, help_text="ISK carried into the period by hand when it was re-opened (0.37.0): one movement, so the period starts from it instead of 0"),
        ),
    ]
