from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("shipyard", "0005_usersettings_bpc_markup"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MemberBlueprintPrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price_isk", models.DecimalField(decimal_places=2, help_text="Blueprint cost per run (ISK) as this member gets it", max_digits=15)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ship", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="member_prices", to="shipyard.ship")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shipyard_bpc_prices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("user", "ship")}},
        ),
    ]
