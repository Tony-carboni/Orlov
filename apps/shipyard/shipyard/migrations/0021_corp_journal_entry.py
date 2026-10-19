"""The executor corp's journal gets its own table; its rows move out of the structure corp's ledger table.

In 0.14.0 both ledgers shared WalletJournalEntry keyed on the entry id alone, and EVE gives a transfer
between two corporations the same id in both journals, so each hourly read relabelled the other's
shared entries. This moves every row labelled with the executor corp into CorpJournalEntry and leaves
the structure corp's rows where they are (the next structure read restores any shared entry it lacks).
"""
from django.conf import settings
from django.db import migrations, models


def move(apps, schema_editor):
    projects_corp = int(getattr(settings, "SHIPYARD_PROJECTS_CORP_ID", 98843356))
    structure_corp = int(getattr(settings, "SHIPYARD_STRUCTURE_CORP_ID", 98635713))
    if projects_corp == structure_corp:
        return
    Old = apps.get_model("shipyard", "WalletJournalEntry")
    New = apps.get_model("shipyard", "CorpJournalEntry")
    rows = Old.objects.filter(corporation_id=projects_corp)
    fields = ["division", "date", "ref_type", "amount", "balance", "first_party_id", "second_party_id", "context_id",
              "context_id_type", "description", "reason", "tax", "tax_receiver_id"]
    New.objects.bulk_create(
        [New(corporation_id=projects_corp, entry_id=r.entry_id, **{f: getattr(r, f) for f in fields}) for r in rows.iterator()],
        batch_size=500, ignore_conflicts=True,
    )
    rows.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0020_corp_wallet_transaction"),
    ]

    operations = [
        migrations.CreateModel(
            name="CorpJournalEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("corporation_id", models.PositiveIntegerField(db_index=True)),
                ("entry_id", models.BigIntegerField()),
                ("division", models.PositiveSmallIntegerField()),
                ("date", models.DateTimeField(db_index=True)),
                ("ref_type", models.CharField(db_index=True, max_length=60)),
                ("amount", models.FloatField(default=0)),
                ("balance", models.FloatField(default=0)),
                ("first_party_id", models.BigIntegerField(default=0)),
                ("second_party_id", models.BigIntegerField(default=0)),
                ("context_id", models.BigIntegerField(default=0)),
                ("context_id_type", models.CharField(blank=True, max_length=40)),
                ("description", models.CharField(blank=True, max_length=500)),
                ("reason", models.CharField(blank=True, max_length=500)),
                ("tax", models.FloatField(default=0)),
                ("tax_receiver_id", models.BigIntegerField(default=0)),
            ],
            options={"ordering": ["-date"], "unique_together": {("corporation_id", "entry_id")}},
        ),
        migrations.RunPython(move, migrations.RunPython.noop),
    ]
