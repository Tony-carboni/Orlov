"""Scrapmetal tab: yield from the skill, per-unit rounding, groups and dashboard rows."""
from django.test import SimpleTestCase, TestCase

from .. import constants
from ..models import MarketLocation, MaterialType, PriceSnapshot, ScrapItem, UserSettings
from ..services import scrapmetal


class YieldTests(SimpleTestCase):
    def test_skill_levels(self):
        self.assertAlmostEqual(scrapmetal.yield_fraction(5), 0.55)
        self.assertAlmostEqual(scrapmetal.yield_fraction(0), 0.50)
        self.assertAlmostEqual(scrapmetal.yield_fraction(3), 0.53)

    def test_minerals_are_rounded_down_per_unit_like_the_sheet(self):
        # the owner's sheet: 100MN Monopropellant Enduring Afterburner at 55 %
        materials = {"34": 17896, "35": 8030, "36": 1002, "37": 44, "38": 22, "39": 2, "40": 1}
        out = scrapmetal.unit_outputs(materials, 0.55)
        self.assertEqual(out, {34: 9842, 35: 4416, 36: 551, 37: 24, 38: 12, 39: 1, 40: 0})

    def test_member_level_or_default(self):
        self.assertEqual(scrapmetal.skill_level(None), 5)
        self.assertEqual(scrapmetal.skill_level(UserSettings()), 5)  # nothing loaded yet: the owner's default
        self.assertEqual(scrapmetal.skill_level(UserSettings(skills_character_id=1, scrapmetal_processing=3)), 3)

    def test_groups_and_variants_from_the_owners_list(self):
        self.assertEqual(scrapmetal.group_of("Heavy Knave Scoped Energy Nosferatu")[0], "Heavy energy nosferatus")
        self.assertEqual(scrapmetal.group_of("'Notos' Compact Medium Proton Smartbomb")[0], "Smartbombs")
        self.assertEqual(scrapmetal.group_of("Not A Module"), (None, None))
        self.assertEqual(scrapmetal.variant_of("Heavy Knave Scoped Energy Nosferatu"), "Scoped")
        self.assertEqual(scrapmetal.variant_of("1400mm Gallium Cannon"), "other")
        self.assertEqual(sum(len(names) for _, names in constants.SCRAP_GROUPS), 66)
        all_names = [n for _, names in constants.SCRAP_GROUPS for n in names]
        self.assertEqual(len(all_names), len(set(all_names)))


class RowTests(TestCase):
    def setUp(self):
        self.market = MarketLocation.objects.create(name="Jita", station_id=60003760, is_default=True)
        MaterialType.objects.create(type_id=34, name="Tritanium")
        MaterialType.objects.create(type_id=35, name="Pyerite")
        PriceSnapshot.objects.create(type_id=34, location=self.market, sell_min=4.0, buy_max=3.5)
        PriceSnapshot.objects.create(type_id=35, location=self.market, sell_min=16.0, buy_max=15.0)
        self.item = ScrapItem.objects.create(type_id=5955, name="100MN Monopropellant Enduring Afterburner", group="100MN afterburners",
                                             group_order=0, variant="Enduring", materials={"34": 1000, "35": 100})
        PriceSnapshot.objects.create(type_id=5955, location=self.market, sell_min=2000.0, buy_max=1500.0, sell_volume=40)

    def test_value_and_ratios(self):
        rows = scrapmetal.dashboard_rows(self.market, UserSettings(skills_character_id=1, scrapmetal_processing=5))
        r = rows[0]
        # 1000 × 0.55 = 550 tritanium × 4 + 55 pyerite × 16 = 2200 + 880 = 3080, no tax
        self.assertAlmostEqual(r.net_value, 3080.0)
        self.assertAlmostEqual(r.sell_ratio, 2000 / 3080)
        self.assertAlmostEqual(r.buy_ratio, 1500 / 3080)
        self.assertAlmostEqual(dict((p, round(v, 2)) for p, v in r.price_points)[90], 2772.0)
        self.assertEqual([o.name for o in r.outputs], ["Tritanium", "Pyerite"])
        self.assertTrue(r.complete)

    def test_missing_price_marks_the_row(self):
        PriceSnapshot.objects.filter(type_id=35).delete()
        r = scrapmetal.dashboard_rows(self.market)[0]
        self.assertFalse(r.complete)
        self.assertEqual(r.missing, 1)

    def test_groups_and_variants_present(self):
        self.assertEqual(scrapmetal.groups_present(), ["100MN afterburners"])
        self.assertEqual(scrapmetal.variants_present(), ["Enduring"])
