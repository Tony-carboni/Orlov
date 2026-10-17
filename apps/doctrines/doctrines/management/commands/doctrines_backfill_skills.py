"""Read the required skills of every type already in the table (and of the skills they name) from EVE.

Run once after the skills check is installed; new fits fetch their requirements on save.
"""

from django.core.management.base import BaseCommand

from ...models import ItemType
from ...services import types


class Command(BaseCommand):
    help = "Fetch the required skills of every known type from ESI (one-off after Doctrines 0.3.0)."

    def handle(self, *args, **options):
        done = 0
        for round_no in range(4):  # the skills a type needs, their prerequisites, and so on
            todo = list(ItemType.objects.filter(skills_fetched_at__isnull=True).values_list("type_id", "name"))
            if not todo:
                break
            for type_id, name in todo:
                if types.fetch_type(type_id, name):
                    done += 1
                types.polite_pause()
            # the skills named by what was just read may be new to the table
            for row in ItemType.objects.filter(skills_fetched_at__isnull=False):
                for skill_id, _ in row.required_skills or []:
                    ItemType.objects.get_or_create(type_id=int(skill_id), defaults={"name": f"skill {skill_id}", "slot": "skill"})
            self.stdout.write(f"round {round_no + 1}: {len(todo)} types read")
        self.stdout.write(self.style.SUCCESS(f"{done} types fetched; {ItemType.objects.filter(skills_fetched_at__isnull=True).count()} left without requirements"))
