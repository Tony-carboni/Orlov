"""0.41.0: the Projects page for the officers who manage the corporation's projects (owner, 2026-11-25)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("shipyard", "0039_corpmemberevent"),
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
                    ("director_access", "Can open the Director page (the corporation's directors)"),
                    ("projects_access", "Can open the Projects page (the officers who manage the corporation's projects)"),
                ),
            },
        ),
    ]
