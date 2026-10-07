from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0004_industry")]

    operations = [
        migrations.AddField(
            model_name="usersettings",
            name="bpc_markup",
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Blueprint markup for this member in % (blank = the corp's default). Managers only; 0 for people who build from their own stash.", max_digits=5, null=True),
        ),
    ]
