# Doctrines 0.2.0: a ship line can carry several fits (T1, T2) of the same hull and role.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("doctrines", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="doctrineship",
            name="variant",
            field=models.CharField(blank=True, help_text="T1, T2, ... when the same hull and role has several fits (lower-skill and full-skill versions); the page lists the hull once and shows the variants on click. Blank = the only fit", max_length=12),
        ),
    ]
