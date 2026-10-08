"""Reprocessing tab: yield formula, families from material signatures, dashboard rows."""
from django.test import SimpleTestCase, TestCase

from ..models import MarketLocation, MaterialType, Ore, OreMarketStats, PriceSnapshot
from ..services import reprocessing
from ..services.reprocessing import family_and_variant, yield_fraction


class YieldTests(SimpleTestCase):
    def test_owners_setup(self):
        # T2-rigged Tatara, high-sec, all skills V, RX-804: (50+3) % × 1.055 × 1.15 × 1.10 × 1.10 × 1.04
        self.assertAlmostEqual(yield_fraction("ore"), 0.8092, places=4)
        self.assertAlmostEqual(yield_fraction("ice"), 0.8092, places=4)
        self.assertAlmostEqual(yield_fraction("moon"), 0.8092, places=4)
        s = reprocessing.setup_summary()
        self.assertEqual(s["price_points"], [90, 92, 95, 98, 100])
        self.assertAlmostEqual(s["tax"], 0.02)


class FamilyTests(SimpleTestCase):
    def test_families_and_variants_from_names(self):
        cases = {
            "Compressed Veldspar": ("Veldspar", "base"),
            "Compressed Veldspar II-Grade": ("Veldspar", "II"),
            "Compressed Veldspar III-Grade": ("Veldspar", "III"),
            "Compressed Veldspar IV-Grade": ("Veldspar", "IV"),
            "Compressed Veldspar 0-Grade": ("Veldspar", "0"),
            "Compressed Dark Ochre II-Grade": ("Dark Ochre", "II"),
            "Compressed Kangite X-Grade": ("Kangite", "X"),
            "Compressed Bezdnacine III-Grade": ("Bezdnacine", "III"),
            "Compressed Blue Ice": ("Blue Ice", "base"),
            "Compressed Blue Ice IV-Grade": ("Blue Ice", "IV"),
            "Compressed Zeolites": ("Zeolites", "base"),
            "Compressed Brimful Zeolites": ("Zeolites", "+15"),
            "Compressed Glistening Zeolites": ("Zeolites", "+100"),
            "Compressed Lavish Chromite": ("Chromite", "+15"),
            "Compressed Shimmering Chromite": ("Chromite", "+100"),
            "Compressed Replete Zircon": ("Zircon", "+15"),
            "Compressed Glowing Zircon": ("Zircon", "+100"),
        }
        for name, expected in cases.items():
            self.assertEqual(family_and_variant(name), expected, name)
        self.assertEqual(reprocessing.variant_label("II"), "II-Grade")
        self.assertEqual(reprocessing.variant_label("+100"), "+100 %")


class RowTests(TestCase):
    def setUp(self):
        self.market = MarketLocation.objects.create(name="Jita", station_id=60003760, is_default=True)
        Ore.objects.create(type_id=62516, name="Compressed Veldspar", group_id=462, group_name="Veldspar", kind="ore",
                           family="Veldspar", variant="base", portion_size=100, volume=0.001, materials={"34": 400})
        Ore.objects.create(type_id=62520, name="Compressed Scordite II-Grade", group_id=461, group_name="Scordite", kind="ore",
                           family="Scordite", variant="II", portion_size=100, volume=0.001, materials={"34": 150, "35": 90})
        MaterialType.objects.create(type_id=34, name="Tritanium")
        MaterialType.objects.create(type_id=35, name="Pyerite")
        PriceSnapshot.objects.create(type_id=34, location=self.market, sell_min=4.0, buy_max=3.8)
        PriceSnapshot.objects.create(type_id=62516, location=self.market, sell_min=12.0, buy_max=11.0, sell_volume=2_469_134.0)
        PriceSnapshot.objects.create(type_id=62520, location=self.market, sell_min=10.0, buy_max=9.0)
        OreMarketStats.objects.create(ore_id=62516, avg_daily_volume=1_234_567.0, avg_price=11.5)

    def test_rows(self):
        rows = {r.ore.name: r for r in reprocessing.dashboard_rows(self.market)}
        v = rows["Compressed Veldspar"]
        y = yield_fraction("ore")
        # 400 tritanium per 100 units → 4 per unit × yield × 4 ISK, minus 2 % tax
        self.assertAlmostEqual(v.outputs[0].quantity, 4 * y, places=6)
        self.assertAlmostEqual(v.gross_value, 16 * y, places=6)
        self.assertAlmostEqual(v.net_value, 16 * y * 0.98, places=6)
        self.assertTrue(v.complete)
        self.assertAlmostEqual(v.sell_ratio, 12.0 / v.net_value)
        self.assertAlmostEqual(v.buy_ratio, 11.0 / v.net_value)
        self.assertEqual((v.avg_daily_volume, v.avg_price), (1_234_567.0, 11.5))
        self.assertAlmostEqual(v.market_depth_days, 2.0)
        self.assertIsNone(rows["Compressed Scordite II-Grade"].market_depth_days)
        self.assertEqual(rows["Compressed Scordite II-Grade"].avg_daily_volume, 0.0)
        self.assertEqual([p for p, _ in v.price_points], [90, 92, 95, 98, 100])
        self.assertAlmostEqual(v.price_points[0][1], v.net_value * 0.9)
        self.assertAlmostEqual(v.price_points[-1][1], v.net_value)
        # Scordite: Pyerite has no price → incomplete, and the priced part still counts
        s = rows["Compressed Scordite II-Grade"]
        self.assertFalse(s.complete)
        self.assertEqual(s.missing, 1)
        self.assertAlmostEqual(s.gross_value, 1.5 * y * 4.0, places=6)
        self.assertEqual(reprocessing.families_by_kind()["ore"], ["Scordite", "Veldspar"])
        self.assertIn(34, reprocessing.output_type_ids())
        self.assertEqual(reprocessing.variants_present(), [("base", "base"), ("II", "II-Grade")])
        # moon ore rarity from the group name
        z = Ore.objects.create(type_id=62463, name="Compressed Zeolites", group_id=1884, group_name="Ubiquitous Moon Asteroids",
                               kind="moon", family="Zeolites", variant="base", portion_size=100, volume=0.1, materials={"16634": 65})
        Ore.objects.create(type_id=62471, name="Compressed Monazite", group_id=1923, group_name="Exceptional Moon Asteroids",
                           kind="moon", family="Monazite", variant="base", portion_size=100, volume=0.1, materials={"16650": 4})
        self.assertEqual(z.rarity, "R4")
        self.assertEqual(Ore.objects.get(type_id=62516).rarity, "")
        self.assertEqual(reprocessing.rarities_present(), ["R4", "R64"])
