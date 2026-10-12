from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0013_reprocessing_access")]

    operations = [
        migrations.AddField(model_name="usersettings", name="repro_skills", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="usersettings", name="repro_implant", field=models.PositiveSmallIntegerField(default=4)),
        migrations.AddField(model_name="usersettings", name="repro_source", field=models.CharField(default="default", help_text="default | manual | esi", max_length=10)),
        migrations.AddField(model_name="usersettings", name="repro_character_name", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="usersettings", name="repro_fetched_at", field=models.DateTimeField(blank=True, null=True)),
    ]
