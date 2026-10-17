# Doctrines 0.2.4: SRP percentage per ship, overriding the doctrine's (logistics at 100 %).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("doctrines", "0003_doctrine_srp_percent"),
    ]

    operations = [
        migrations.AddField(
            model_name="doctrineship",
            name="srp_percent",
            field=models.PositiveSmallIntegerField(blank=True, help_text="SRP for this ship as a percentage of its cost; blank = the doctrine's percentage (e.g. 100 for logistics in a 50 % doctrine)", null=True),
        ),
    ]
