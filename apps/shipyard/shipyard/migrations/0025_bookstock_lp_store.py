# Shipyard 0.18.0: LP store redemptions as stock batches (LP used, input items, the offer's ISK).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0024_corpjournal_division_key"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookstock", name="unit_cost",
            field=models.FloatField(blank=True, null=True, help_text="Buy value per unit, ISK, for a purchase. Leave empty for an LP store redemption: its cost is worked out from the LP, the input items and the ISK below"),
        ),
        migrations.AlterField(model_name="bookstock", name="bought_at", field=models.DateTimeField(help_text="When it was bought or redeemed (EVE time)")),
        migrations.AddField(model_name="bookstock", name="lp_used", field=models.PositiveIntegerField(default=0, help_text="LP store redemption: LP used, valued at what the corp paid per LP")),
        migrations.AddField(model_name="bookstock", name="input_type_id", field=models.PositiveIntegerField(blank=True, null=True, help_text="LP store redemption: the item the offer takes in (e.g. 11289 Cap Booster 800), used from the corp's stock")),
        migrations.AddField(model_name="bookstock", name="input_units", field=models.BigIntegerField(default=0, help_text="LP store redemption: how many of that item")),
        migrations.AddField(model_name="bookstock", name="isk_paid", field=models.FloatField(default=0, help_text="LP store redemption: the ISK part of the offers")),
        migrations.AddField(model_name="bookstock", name="isk_paid_by", field=models.CharField(choices=[("outside", "A character's own wallet (a contribution to the corp)"), ("corp", "A corporation wallet")], default="outside", max_length=10)),
    ]
