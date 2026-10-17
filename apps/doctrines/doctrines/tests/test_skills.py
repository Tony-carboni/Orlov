"""The skills check: requirements from dogma, prerequisites, the gap, the page, the character switch."""
from unittest import mock

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ..models import Category, Doctrine, DoctrineShip, ItemType, MemberCharacter
from ..services import fittings, skills, types

FIT = "[Rifter, Rifter T1]\n150mm Light Prototype Automatic Cannon\nDamage Control I\n"
NOW = timezone.now()


def _type(tid, name, slot, reqs=()):
    return ItemType.objects.create(type_id=tid, name=name, slot=slot, required_skills=[list(r) for r in reqs], skills_fetched_at=NOW)


class RequirementTests(TestCase):
    def setUp(self):
        # skills: Gunnery (3300), Small Projectile Turret (3303, needs Gunnery I), Minmatar Frigate (3329, needs Spaceship Command I),
        # Spaceship Command (3327), Hull Upgrades (3394, needs Mechanics I), Mechanics (3392)
        _type(3300, "Gunnery", "skill")
        _type(3303, "Small Projectile Turret", "skill", [(3300, 1)])
        _type(3327, "Spaceship Command", "skill")
        _type(3329, "Minmatar Frigate", "skill", [(3327, 1)])
        _type(3392, "Mechanics", "skill")
        _type(3394, "Hull Upgrades", "skill", [(3392, 1)])
        _type(587, "Rifter", "ship", [(3329, 1)])
        _type(2873, "150mm Light Prototype Automatic Cannon", "high", [(3303, 2)])
        _type(2046, "Damage Control I", "low", [(3394, 1)])

    def test_dogma_attributes_become_required_skills(self):
        info = {"dogma_attributes": [{"attribute_id": 182, "value": 3303.0}, {"attribute_id": 277, "value": 2.0},
                                     {"attribute_id": 183, "value": 3300.0}, {"attribute_id": 278, "value": 1.0},
                                     {"attribute_id": 999, "value": 7.0}]}
        self.assertEqual(types.required_skills_of(info), [[3303, 2], [3300, 1]])

    def test_requirements_include_prerequisites_at_the_highest_level(self):
        reqs = skills.requirements({587, 2873, 2046})
        self.assertEqual(reqs[3303]["level"], 2)
        self.assertEqual(reqs[3300]["level"], 1)  # Gunnery through Small Projectile Turret
        self.assertEqual(reqs[3327]["level"], 1)  # Spaceship Command through Minmatar Frigate
        self.assertIn("150mm Light Prototype Automatic Cannon", reqs[3303]["for"])
        self.assertIn("Small Projectile Turret", reqs[3300]["for"])

    def test_check_lists_the_gap_highest_first(self):
        have = {"3329": 1, "3327": 3, "3303": 1, "3300": 5}
        result = skills.check({587, 2873, 2046}, have)
        self.assertFalse(result["ok"])
        names = [m["name"] for m in result["missing"]]
        self.assertEqual(names[:1], ["Hull Upgrades"])  # need I, have 0: gap 1, same as the turret; alphabetical then
        self.assertIn("Small Projectile Turret", names)
        self.assertIn("Mechanics", names)
        self.assertNotIn("Gunnery", names)
        turret = next(m for m in result["missing"] if m["name"] == "Small Projectile Turret")
        self.assertEqual((turret["need_roman"], turret["have_roman"]), ("II", "I"))
        self.assertEqual(result["total"], 6)

    def test_everything_trained_is_ok(self):
        have = {sid: 5 for sid in (3300, 3303, 3327, 3329, 3392, 3394)}
        self.assertTrue(skills.check({587, 2873, 2046}, have)["ok"])


@override_settings(DOCTRINES_HOST="")
class SkillsPageTests(TestCase):
    def setUp(self):
        self.user = AuthUtils.create_user("pilot")
        AuthUtils.add_main_character_2(self.user, "Pilot Main", 1001, corp_id=2001, corp_name="Corp", corp_ticker="CORP")
        self.main = EveCharacter.objects.get(character_id=1001)
        self.user = AuthUtils.add_permission_to_user_by_name("doctrines.basic_access", self.user)
        # add_main_character_2 does not create the ownership the switch and use_character read
        CharacterOwnership.objects.get_or_create(character=self.main, defaults={"user": self.user, "owner_hash": "pilot-main"})
        _type(3300, "Gunnery", "skill")
        _type(3303, "Small Projectile Turret", "skill", [(3300, 1)])
        _type(3327, "Spaceship Command", "skill")
        _type(3329, "Minmatar Frigate", "skill", [(3327, 1)])
        _type(3392, "Mechanics", "skill")
        _type(3394, "Hull Upgrades", "skill", [(3392, 1)])
        _type(587, "Rifter", "ship", [(3329, 1)])
        _type(2873, "150mm Light Prototype Automatic Cannon", "high", [(3303, 2)])
        _type(2046, "Damage Control I", "low", [(3394, 1)])
        light = Category.objects.create(name="Light & cheap", order=1)
        self.doc = Doctrine.objects.create(category=light, name="AB Armor frigs", gameplay="Faction warfare")
        ship = DoctrineShip(doctrine=self.doc, name="Rifter T1", role="DPS", variant="T1", fitting_text=FIT)
        fittings.store(ship)
        ship.save()
        self.client.force_login(self.user)

    def test_without_a_character_the_page_invites_to_choose(self):
        html = self.client.get(reverse("doctrines:doctrine", args=[self.doc.slug])).content.decode()
        self.assertIn("Choose a character", html)
        self.assertIn("Pilot Main", html)  # offered in the switch

    def test_with_a_character_the_missing_skills_show(self):
        MemberCharacter.objects.create(user=self.user, character_id=1001, character_name="Pilot Main", fetched_at=NOW,
                                       skills={"3329": 1, "3327": 1, "3303": 1, "3300": 1})
        r = self.client.get(reverse("doctrines:doctrine", args=[self.doc.slug]))
        html = r.content.decode()
        self.assertIn("Skills check for", html)
        self.assertIn("Hull Upgrades", html)
        self.assertIn("Small Projectile Turret", html)
        self.assertIn("3 skills", html)  # the ships table's Skills column: Hull Upgrades, Mechanics, Small Projectile Turret
        self.assertEqual(r.context["rows"][0]["skills"]["count"], 3)

    def test_use_character_without_a_token_goes_to_eve_login(self):
        with mock.patch("doctrines.views.skills.token_for", return_value=None), \
             mock.patch("doctrines.views.sso_redirect", return_value=HttpResponse("sso")) as sso:
            r = self.client.post(reverse("doctrines:use_character", args=[1001]), {"next": self.doc.slug})
        self.assertEqual(r.content, b"sso")
        self.assertEqual(sso.call_args.kwargs["scopes"], skills.SCOPES)
        self.assertEqual(self.client.session["doctrines_sso_pending"], 1001)

    def test_use_character_with_a_token_loads_and_returns(self):
        fake = mock.Mock(character_id=1001, character_name="Pilot Main")
        with mock.patch("doctrines.views.skills.token_for", return_value=fake), \
             mock.patch("doctrines.views.skills.esi_skills", return_value=({"3300": 5}, 1234567)):
            r = self.client.post(reverse("doctrines:use_character", args=[1001]), {"next": self.doc.slug})
        self.assertRedirects(r, reverse("doctrines:doctrine", args=[self.doc.slug]), fetch_redirect_response=False)
        mc = MemberCharacter.objects.get(user=self.user)
        self.assertEqual((mc.character_name, mc.skills, mc.total_sp), ("Pilot Main", {"3300": 5}, 1234567))

    def test_another_members_character_is_refused(self):
        other = AuthUtils.create_user("someone")
        AuthUtils.add_main_character_2(other, "Someone Else", 1002, corp_id=2001, corp_name="Corp", corp_ticker="CORP")
        r = self.client.post(reverse("doctrines:use_character", args=[1002]), {"next": self.doc.slug})
        self.assertEqual(r.status_code, 404)
