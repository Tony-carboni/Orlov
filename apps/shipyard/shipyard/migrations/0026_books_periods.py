# Shipyard 0.20.0: the books baseline becomes a reporting period with its opening figures.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0025_bookstock_lp_store"),
    ]

    operations = [
        migrations.AlterModelOptions(name="booksbaseline", options={"ordering": ["taken_at"], "verbose_name": "books period", "verbose_name_plural": "books periods"}),
        migrations.AlterField(model_name="booksbaseline", name="taken_at", field=models.DateTimeField(help_text="The period's start (EVE time): the budget baseline, or the date of a State of the Alliance post")),
        migrations.AlterField(model_name="booksbaseline", name="loan", field=models.FloatField(help_text="The working budget lent by the owner, ISK (the same on every row)")),
        migrations.AlterField(model_name="booksbaseline", name="wallet", field=models.FloatField(help_text="Master wallet (division 1) at the start, ISK")),
        migrations.AlterField(model_name="booksbaseline", name="pool", field=models.FloatField(help_text="Reward ISK in the active projects at the start, ISK")),
        migrations.AddField(model_name="booksbaseline", name="other_divs", field=models.FloatField(default=0, help_text="Wallet divisions 2 to 6 at the start, ISK")),
        migrations.AddField(model_name="booksbaseline", name="held", field=models.FloatField(default=0, help_text="Goods from project buybacks held at the start, at what the projects paid")),
        migrations.AddField(model_name="booksbaseline", name="open_escrow", field=models.FloatField(default=0, help_text="ISK in open buy orders at the start")),
        migrations.AddField(model_name="booksbaseline", name="lp_units", field=models.IntegerField(default=0, help_text="Loyalty points held at the start")),
        migrations.AddField(model_name="booksbaseline", name="lp_cost", field=models.FloatField(default=0, help_text="What those loyalty points cost, ISK")),
        migrations.AddField(model_name="booksbaseline", name="opening_result", field=models.FloatField(default=0, help_text="Assets above the loan at the start, ISK (0 for the budget baseline)")),
        migrations.AddField(model_name="booksbaseline", name="source", field=models.CharField(blank=True, help_text="What opened the period: the State of the Alliance post's title and date", max_length=200)),
    ]
