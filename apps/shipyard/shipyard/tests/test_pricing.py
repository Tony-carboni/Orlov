from django.test import SimpleTestCase, TestCase

from .. import constants
from ..models import Facility, LpFaction, MarketLocation, Ship, ShipConfig, UserSettings
from ..services import catalog, everef, pricing
from ..templatetags import shipyard_tags as tags


class TaxRateTests(SimpleTestCase):
    def test_npc_station_with_skills(self):
        market = MarketLocation(sales_tax_base=7.5, broker_fee_base=3.0, is_npc_station=True)
        s = UserSettings(accounting=5, broker_relations=5)
        r = pricing.tax_rates(market, s)
        self.assertAlmostEqual(r.sales_tax, 0.075 * (1 - 0.55), places=6)
        self.assertAlmostEqual(r.broker_fee, 0.03 - 0.015, places=6)

    def test_manual_override_wins(self):
        market = MarketLocation(sales_tax_base=7.5, broker_fee_base=3.0, is_npc_station=True)
        s = UserSettings(accounting=0, manual_sales_tax=4.81, manual_broker_fee=1.0)
        r = pricing.tax_rates(market, s)
        self.assertAlmostEqual(r.sales_tax, 0.0481)
        self.assertAlmostEqual(r.broker_fee, 0.01)

    def test_player_structure_ignores_broker_relations(self):
        market = MarketLocation(sales_tax_base=7.5, broker_fee_base=1.0, is_npc_station=False)
        s = UserSettings(broker_relations=5)
        self.assertAlmostEqual(pricing.tax_rates(market, s).broker_fee, 0.01)


class EconomicsTests(SimpleTestCase):
    """Reproduce the owner's spreadsheet for the Vindicator (2026-10-07)."""

    def test_vindicator_like_sheet(self):
        # sheet: input cost 818.1 M, job cost 17,985,640, BPC 23 M, sales tax 4.81 %, sell 999.9 M → profit 92.68 M
        rates = pricing.TaxRates(sales_tax=0.0481, broker_fee=0.0)
        config = ShipConfig(bpc_price_isk=23_000_000, tag_cost_isk=0)
        econ = pricing.economics(
            sell_price=999_900_000,
            material_rows=[{"type_id": 34, "quantity": 1000}],
            prices={34: 818_135_381.32 / 1000},
            names={34: "Tritanium"}, volumes={34: 0.01},
            job_cost=17_985_640.74,
            config=config, use_lp=False, rates=rates,
            avg_daily_volume=7.57, sell_volume_on_market=53,
        )
        self.assertAlmostEqual(econ.material_cost, 818_135_381.32, places=2)
        self.assertAlmostEqual(econ.sales_tax, 48_095_190, places=0)
        self.assertAlmostEqual(econ.net_profit, 92_683_787.94, places=0)
        self.assertAlmostEqual(econ.margin, 0.0927, places=3)
        self.assertAlmostEqual(econ.market_depth_days, 7.0, places=1)
        self.assertTrue(econ.complete)

    def test_missing_price_marks_incomplete(self):
        rates = pricing.TaxRates(sales_tax=0.03, broker_fee=0.01)
        econ = pricing.economics(
            sell_price=100.0, material_rows=[{"type_id": 1, "quantity": 2}], prices={},
            names={}, volumes={}, job_cost=1, config=None, use_lp=False, rates=rates,
        )
        self.assertEqual(econ.missing_prices, 1)
        self.assertFalse(econ.complete)
        self.assertEqual(econ.bpc_cost, 0.0)

    def test_no_sell_price(self):
        rates = pricing.TaxRates(sales_tax=0.03, broker_fee=0.01)
        econ = pricing.economics(sell_price=None, material_rows=[], prices={}, names={}, volumes={},
                                 job_cost=0, config=None, use_lp=False, rates=rates)
        self.assertIsNone(econ.net_profit)
        self.assertIsNone(econ.margin)
        self.assertIsNone(econ.market_depth_days)


class BlueprintCostTests(TestCase):
    def test_lp_pricing(self):
        ship = Ship.objects.create(type_id=1, name="X", group_id=25, hull_size="Frigate", category="Navy", blueprint_type_id=2)
        lp = LpFaction.objects.create(name="Caldari Navy", isk_per_lp=1500)
        cfg = ShipConfig.objects.create(ship=ship, bpc_price_isk=50_000_000, lp_faction=lp, lp_cost=20_000, lp_isk_cost=20_000_000, lp_runs=2)
        self.assertEqual(pricing.blueprint_cost(cfg, use_lp=False), (50_000_000.0, "manual"))
        price, src = pricing.blueprint_cost(cfg, use_lp=True)
        self.assertEqual(src, "lp")
        self.assertAlmostEqual(price, (20_000 * 1500 + 20_000_000) / 2)

    def test_tag_priced_from_market(self):
        ship = Ship.objects.create(type_id=1, name="X", group_id=26, hull_size="Cruiser", category="Navy", blueprint_type_id=2)
        lp = LpFaction.objects.create(name="Caldari Navy", isk_per_lp=900)
        cfg = ShipConfig.objects.create(ship=ship, lp_faction=lp, lp_cost=18_000, tag_type_id=17244, tag_quantity=1)
        self.assertEqual(cfg.tag_cost(570_800), (570_800.0, False))
        self.assertEqual(cfg.tag_cost(None), (0.0, True))  # price not fetched yet
        cfg.tag_cost_isk = 1_000
        cfg.lp_runs = 2
        cost, missing = cfg.tag_cost(570_800)
        self.assertAlmostEqual(cost, 1_000 + 570_800 / 2)
        self.assertFalse(missing)
        # without a tag type only the hand-typed extras count
        cfg.tag_type_id = None
        self.assertEqual(cfg.tag_cost(None), (1_000.0, False))

    def test_economics_marks_missing_tag_price(self):
        ship = Ship.objects.create(type_id=1, name="X", group_id=26, hull_size="Cruiser", category="Navy", blueprint_type_id=2)
        cfg = ShipConfig.objects.create(ship=ship, tag_type_id=17244)
        rates = pricing.TaxRates(sales_tax=0.0, broker_fee=0.0)
        e = pricing.economics(sell_price=10.0, material_rows=[{"type_id": 34, "quantity": 1}], prices={34: 1.0},
                              names={}, volumes={}, job_cost=0, config=cfg, use_lp=False, rates=rates)
        self.assertEqual(e.missing_prices, 1)
        self.assertFalse(e.complete)
        e = pricing.economics(sell_price=10.0, material_rows=[{"type_id": 34, "quantity": 1}], prices={34: 1.0},
                              names={}, volumes={}, job_cost=0, config=cfg, use_lp=False, rates=rates, tag_unit_price=3.0)
        self.assertEqual(e.missing_prices, 0)
        self.assertEqual(e.tag_cost, 3.0)
        self.assertTrue(e.complete)

    def test_blueprint_policy_by_category(self):
        ship = Ship.objects.create(type_id=1, name="X", group_id=26, hull_size="Cruiser", category="Navy", blueprint_type_id=2)
        lp = LpFaction.objects.create(name="Caldari Navy", isk_per_lp=900)
        cfg = ShipConfig.objects.create(ship=ship, bpc_price_isk=5_000_000, lp_faction=lp, lp_cost=18_000)
        rates = pricing.TaxRates(sales_tax=0.0, broker_fee=0.0)
        # navy: LP price plus the corp's markup, on the tag too
        self.assertEqual(pricing.blueprint_cost(cfg, use_lp=True, category="Navy"), (18_000 * 900 * 1.05, "lp"))
        cfg.tag_type_id = 17244
        e = pricing.economics(sell_price=100.0, material_rows=[], prices={}, names={}, volumes={}, job_cost=0,
                              config=cfg, use_lp=True, rates=rates, tag_unit_price=1_000.0, category="Navy")
        self.assertAlmostEqual(e.tag_cost, 1_050.0)
        self.assertAlmostEqual(e.bpc_markup, 0.05)
        self.assertFalse(e.bpc_excluded)
        # base: free, whatever is typed; except battleships, which members source themselves
        self.assertEqual(pricing.blueprint_cost(cfg, use_lp=True, category="Base"), (0.0, "free"))
        self.assertEqual(pricing.blueprint_cost(cfg, use_lp=True, category="Base", hull_size="Cruiser"), (0.0, "free"))
        self.assertEqual(pricing.blueprint_cost(cfg, use_lp=True, category="Base", hull_size="Battleship"), (0.0, "public"))
        # pirate / trig / edencom: no source, blueprint and its tags left out, profit marked
        for cat in ("Pirate", "Trig", "Edencom"):
            self.assertEqual(pricing.blueprint_cost(cfg, use_lp=True, category=cat), (0.0, "public"))
        e = pricing.economics(sell_price=100.0, material_rows=[], prices={}, names={}, volumes={}, job_cost=0,
                              config=cfg, use_lp=True, rates=rates, tag_unit_price=None, category="Pirate")
        self.assertTrue(e.bpc_excluded)
        self.assertEqual((e.bpc_cost, e.tag_cost, e.missing_prices), (0.0, 0.0, 0))
        # no category (simulation with a typed price): plain LP/manual choice, no markup
        self.assertEqual(pricing.blueprint_cost(cfg, use_lp=False), (5_000_000.0, "manual"))

    def test_lp_pricing_falls_back_without_offer(self):
        ship = Ship.objects.create(type_id=1, name="X", group_id=25, hull_size="Frigate", category="Base", blueprint_type_id=2)
        cfg = ShipConfig.objects.create(ship=ship, bpc_price_isk=1_000)
        self.assertEqual(pricing.blueprint_cost(cfg, use_lp=True), (1_000.0, "manual"))


class CatalogTests(SimpleTestCase):
    def _t(self, **kw):
        base = {"type_id": 1, "name": {"en": "Test"}, "published": True, "group_id": 27, "meta_group_id": 1,
                "faction_id": 500004, "produced_by_blueprints": {"2": {"blueprint_type_id": 2, "blueprint_activity": "manufacturing"}},
                "packaged_volume": 50000}
        base.update(kw)
        return base

    def test_base_navy_pirate(self):
        self.assertEqual(catalog.classify(self._t())["category"], constants.CAT_BASE)
        self.assertEqual(catalog.classify(self._t(meta_group_id=4))["category"], constants.CAT_NAVY)
        self.assertEqual(catalog.classify(self._t(meta_group_id=4, faction_id=500020))["category"], constants.CAT_PIRATE)
        self.assertEqual(catalog.classify(self._t(meta_group_id=None, faction_id=500026))["category"], constants.CAT_TRIG)
        self.assertEqual(catalog.classify(self._t(faction_id=500027))["category"], constants.CAT_EDENCOM)
        self.assertEqual(catalog.classify(self._t(group_id=463, faction_id=500014))["category"], constants.CAT_BASE)
        self.assertEqual(catalog.classify(self._t(group_id=25, meta_group_id=4, faction_id=500014))["category"], constants.CAT_ORE)

    def test_industrial_group(self):
        self.assertEqual(constants.HULL_GROUPS[28], "Industrial")
        self.assertEqual(constants.HULL_GROUPS[941], "Industrial")
        self.assertEqual(constants.HULL_GROUPS[463], "Barge")
        self.assertIn("Orca", constants.INACTIVE_BY_DEFAULT)

    def test_hull_size_and_exclusions(self):
        self.assertEqual(catalog.classify(self._t(group_id=1201))["hull_size"], "Battlecruiser")
        self.assertIsNone(catalog.classify(self._t(group_id=30)))  # titan group
        self.assertIsNone(catalog.classify(self._t(meta_group_id=2)))  # tech II
        self.assertIsNone(catalog.classify(self._t(produced_by_blueprints={})))
        self.assertIsNone(catalog.classify(self._t(published=False)))
        row = catalog.classify(self._t(name={"en": "Gnosis"}, faction_id=500017))
        self.assertEqual(row["category"], constants.CAT_OTHER)
        self.assertFalse(row["default_active"])
        row = catalog.classify(self._t(name={"en": "Apocalypse Imperial Issue"}, meta_group_id=4, faction_id=500003))
        self.assertFalse(row["default_active"])


class EverefParsingTests(SimpleTestCase):
    def test_duration(self):
        self.assertEqual(everef.parse_duration("PT2H18M43S"), 2 * 3600 + 18 * 60 + 43)
        self.assertEqual(everef.parse_duration("P1DT2H"), 86400 + 7200)
        self.assertEqual(everef.parse_duration(""), 0)

    def test_normalise(self):
        block = {"materials": {"34": {"quantity": 10, "cost": 1}, "35": {"quantity": 20}}, "estimated_item_value": 5,
                 "total_job_cost": 7, "system_cost_index": 6, "scc_surcharge": 1, "facility_tax": 0,
                 "time_per_run": "PT1H", "materials_volume": 3}
        d = everef.normalise_cost_block(block)
        self.assertEqual(d["materials"][0], {"type_id": 35, "quantity": 20.0})
        self.assertEqual(d["job_cost"], 7.0)
        self.assertEqual(d["time_seconds"], 3600)


class TemplateTagTests(SimpleTestCase):
    def test_isk(self):
        self.assertEqual(tags.isk(92_683_787), "92.7 M")
        self.assertEqual(tags.isk(1_234_000_000, 2), "1.23 B")
        self.assertEqual(tags.isk(-5_000), "-5.0 k")
        self.assertEqual(tags.isk(None), "–")

    def test_pct_depth_duration(self):
        self.assertEqual(tags.pct(0.0927), "9.3 %")
        self.assertEqual(tags.depth(7.04), "7.0")
        self.assertEqual(tags.depth(5000), "999+")
        self.assertEqual(tags.duration(8323), "2h 18m")
        self.assertEqual(tags.duration(90000), "1d 1h")


class FacilityTests(SimpleTestCase):
    def test_rig_names(self):
        f = Facility(rig_type_ids=[37154, 99999])
        self.assertEqual(f.rig_names[0], constants.RIG_TYPES[37154])
        self.assertEqual(f.rig_names[1], "Rig 99999")
