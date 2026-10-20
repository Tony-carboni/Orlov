# Shipyard 0.17.1: the corp journal's key includes the division. A transfer between two wallet
# divisions has the same entry id in both journals; until now only the first division's side was kept.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0023_books"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="corpjournalentry",
            unique_together={("corporation_id", "division", "entry_id")},
        ),
    ]
