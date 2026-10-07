from django.db import migrations, models

JITA_44 = 60003760
CALDARI_NAVY = 1000035
CALDARI_STATE = 500001


def set_jita_owner(apps, schema_editor):
    MarketLocation = apps.get_model("shipyard", "MarketLocation")
    MarketLocation.objects.filter(station_id=JITA_44, owner_corporation_id__isnull=True).update(
        owner_corporation_id=CALDARI_NAVY, owner_faction_id=CALDARI_STATE
    )


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0002_shipconfig_tag_type")]

    operations = [
        migrations.AddField(
            model_name="marketlocation",
            name="owner_corporation_id",
            field=models.PositiveIntegerField(blank=True, help_text="NPC corporation that owns the station (Jita 4-4: Caldari Navy 1000035); the member's standing with it lowers the broker fee", null=True),
        ),
        migrations.AddField(
            model_name="marketlocation",
            name="owner_faction_id",
            field=models.PositiveIntegerField(blank=True, help_text="Faction of that corporation (Caldari State 500001); the member's standing with it lowers the broker fee", null=True),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="standings",
            field=models.JSONField(blank=True, default=dict, help_text="Unmodified standings of the skills character, {entity id: standing}, read from ESI with the skills"),
        ),
        migrations.AddField(
            model_name="usersettings",
            name="standings_fetched_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(set_jita_owner, migrations.RunPython.noop),
    ]
