from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("shipyard", "0014_usersettings_repro_skills")]

    operations = [
        migrations.AlterModelOptions(
            name="general",
            options={
                "default_permissions": (),
                "managed": False,
                "permissions": (
                    ("basic_access", "Can access the Shipyard dashboard"),
                    ("reprocessing_access", "Can use the Reprocessing tab only (no other Shipyard pages)"),
                    ("dashboard_access", "Can use the ship dashboard and My settings only (no other Shipyard pages)"),
                    ("manage_shipyard", "Can edit blueprint prices, LP prices and facilities"),
                    ("view_corp_industry", "Can see the industry of everyone in their corporation"),
                    ("view_alliance_industry", "Can see the industry of everyone in the alliance"),
                ),
            },
        ),
    ]
