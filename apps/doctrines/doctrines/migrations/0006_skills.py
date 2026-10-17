from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("doctrines", "0005_doctrine_composition"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="itemtype",
            name="required_skills",
            field=models.JSONField(blank=True, default=list, help_text="[[skill type id, level], ...] straight from the type's dogma attributes"),
        ),
        migrations.AddField(
            model_name="itemtype",
            name="skills_fetched_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="MemberCharacter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("character_id", models.PositiveIntegerField()),
                ("character_name", models.CharField(max_length=100)),
                ("skills", models.JSONField(blank=True, default=dict, help_text="{skill type id: active level} from ESI")),
                ("total_sp", models.BigIntegerField(default=0)),
                ("fetched_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="doctrines_character", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "member's character", "verbose_name_plural": "members' characters"},
        ),
    ]
