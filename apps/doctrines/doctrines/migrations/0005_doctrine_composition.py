# Doctrines 0.2.5: the target ratio of the roles on the doctrine card.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("doctrines", "0004_doctrineship_srp_percent"),
    ]

    operations = [
        migrations.AddField(
            model_name="doctrine",
            name="composition",
            field=models.TextField(blank=True, help_text="Target ratio of the roles, one per line as 'Role: number', e.g. 'DPS: 5', 'Logistics: 3', 'Tackle: 1', 'Support: 1'. Shown on the card."),
        ),
    ]
