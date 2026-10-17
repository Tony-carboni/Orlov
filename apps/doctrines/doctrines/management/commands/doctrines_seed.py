"""Seed the four categories, four SRP levels and a landing text placeholder (owner's layout, 2026-10-17).
Safe to run again: existing rows are left as they are."""

from django.core.management.base import BaseCommand

from ...models import Category, SiteText, SrpLevel

CATEGORIES = [
    ("Light & cheap", "Frigates and destroyers anyone can fly and lose without a second thought"),
    ("Bread and butter", "The fleets we fly most; the first doctrines to train for"),
    ("Support", "Logistics, boosts, EWAR and scouts that every fleet above needs"),
    ("APEX", "The expensive end: capital-adjacent and faction hulls, by invitation of the FC"),
]

SRP_LEVELS = [
    ("Full", "Hull and fit replaced in full when lost on a called fleet", "success"),
    ("Partial", "Hull replaced, fit at the pilot's cost", "warning"),
    ("Logi only", "Replaced only when flown as the fleet's logistics", "info"),
    ("None", "No replacement: fly it on your own ISK", "secondary"),
]


class Command(BaseCommand):
    help = "Create the doctrine categories, SRP levels and the landing text if they do not exist yet"

    def handle(self, *args, **options):
        for order, (name, blurb) in enumerate(CATEGORIES, start=1):
            _, created = Category.objects.get_or_create(name=name, defaults={"order": order, "blurb": blurb})
            self.stdout.write(f"category {name}: {'created' if created else 'exists'}")
        for order, (name, description, colour) in enumerate(SRP_LEVELS, start=1):
            _, created = SrpLevel.objects.get_or_create(name=name, defaults={"order": order, "description": description, "colour": colour})
            self.stdout.write(f"SRP level {name}: {'created' if created else 'exists'}")
        if not SiteText.objects.exists():
            SiteText.objects.create(
                title="How we fly",
                body=(
                    "Write the alliance's fleet philosophy here (auth admin → Doctrines → Landing page text): what we fly, why, "
                    "and how a new pilot picks a doctrine.\n\n- Light & cheap: start here\n- Bread and butter: train for these\n"
                    "- Support: every fleet needs them\n- APEX: by invitation"
                ),
            )
            self.stdout.write("landing text: created (placeholder)")
        else:
            self.stdout.write("landing text: exists")
