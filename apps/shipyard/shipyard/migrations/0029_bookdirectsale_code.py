import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0028_bookdirectsale"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookdirectsale",
            name="entry_id",
            field=models.BigIntegerField(blank=True, help_text="The journal entry of the deposit, once it appeared", null=True),
        ),
        migrations.AddField(model_name="bookdirectsale", name="code", field=models.CharField(blank=True, db_index=True, default="", help_text="DS-XXXX: the deposit's reason carries it", max_length=10)),
        migrations.AddField(model_name="bookdirectsale", name="lines", field=models.JSONField(blank=True, default=list, help_text="The quoted lines: type id, name, quantity, unit price, line, cost")),
        migrations.AddField(model_name="bookdirectsale", name="quote", field=models.FloatField(default=0, help_text="ISK the sale was quoted at")),
        migrations.AddField(model_name="bookdirectsale", name="cost", field=models.FloatField(default=0, help_text="What the projects paid for the goods, at registration")),
        migrations.AddField(model_name="bookdirectsale", name="created_at", field=models.DateTimeField(default=django.utils.timezone.now)),
        migrations.AddField(model_name="bookdirectsale", name="created_by", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="bookdirectsale", name="matched_at", field=models.DateTimeField(blank=True, null=True)),
    ]
