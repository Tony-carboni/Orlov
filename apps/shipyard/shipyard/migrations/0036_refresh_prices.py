# Shipyard 0.37.0: the refresh_prices permission (the Refresh button on the dashboards without the manager rights; owner, for Hamu).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0035_bargainprefs"),
    ]

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
                    ("books_access", "Can see the corporation's balance sheet (Finance tab)"),
                    ("refresh_prices", "Can press Refresh on the dashboards (queues the Jita price refreshes, nothing else)"),
                ),
            },
        ),
    ]
