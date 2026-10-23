# Shipyard 0.27.0: the projects hangar as read from EVE.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0031_lpsnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="HangarItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("type_id", models.PositiveIntegerField(db_index=True)),
                ("name", models.CharField(blank=True, max_length=100)),
                ("quantity", models.BigIntegerField(default=0)),
                ("location_id", models.BigIntegerField(help_text="The office's station or structure")),
                ("location_flag", models.CharField(help_text="CorpSAG1 to CorpSAG7 (hangar divisions 1 to 7) or CorpDeliveries", max_length=40)),
                ("read_at", models.DateTimeField()),
            ],
            options={"verbose_name": "hangar item", "verbose_name_plural": "hangar items (last read)"},
        ),
    ]
