from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipyard", "0029_bookdirectsale_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookignoredentry",
            name="amount",
            field=models.FloatField(blank=True, help_text="ISK of the line to leave out, as a positive number; empty = the whole line. The rest stays in the books (a deposit that settles a mistake and brings some real money as well)", null=True),
        ),
    ]
