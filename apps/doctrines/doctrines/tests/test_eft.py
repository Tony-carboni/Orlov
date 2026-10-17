"""The fitting parser, the slot layout, the cost and the text export, on a fitting as the game exports it."""
from django.test import SimpleTestCase

from ..services import eft, types
from ..templatetags.doctrines_tags import isk_auto, keyed

HARPY = """[Harpy, Rail Harpy v3]
Magnetic Field Stabilizer II
Magnetic Field Stabilizer II
Damage Control II

5MN Y-T8 Compact Microwarpdrive
Medium Shield Extender II
Multispectrum Shield Hardener II
Warp Disruptor II

150mm Railgun II, Spike S
150mm Railgun II, Spike S
150mm Railgun II, Spike S
150mm Railgun II, Spike S
[Empty High slot]

Small Core Defense Field Extender II
Small Hybrid Collision Accelerator II

Hobgoblin II x2

Spike S x1000
Caldari Navy Antimatter Charge S x1000
Nanite Repair Paste x50
"""

TYPES = {
    "harpy": {"type_id": 11381, "name": "Harpy", "slot": "ship", "volume": 2500},
    "magnetic field stabilizer ii": {"type_id": 10190, "name": "Magnetic Field Stabilizer II", "slot": "low", "volume": 5},
    "damage control ii": {"type_id": 2048, "name": "Damage Control II", "slot": "low", "volume": 5},
    "5mn y-t8 compact microwarpdrive": {"type_id": 5973, "name": "5MN Y-T8 Compact Microwarpdrive", "slot": "mid", "volume": 10},
    "medium shield extender ii": {"type_id": 3831, "name": "Medium Shield Extender II", "slot": "mid", "volume": 10},
    "multispectrum shield hardener ii": {"type_id": 2281, "name": "Multispectrum Shield Hardener II", "slot": "mid", "volume": 5},
    "warp disruptor ii": {"type_id": 3244, "name": "Warp Disruptor II", "slot": "mid", "volume": 5},
    "150mm railgun ii": {"type_id": 3074, "name": "150mm Railgun II", "slot": "high", "volume": 5},
    "spike s": {"type_id": 12814, "name": "Spike S", "slot": "charge", "volume": 0.0125},
    "small core defense field extender ii": {"type_id": 31794, "name": "Small Core Defense Field Extender II", "slot": "rig", "volume": 5},
    "small hybrid collision accelerator ii": {"type_id": 31524, "name": "Small Hybrid Collision Accelerator II", "slot": "rig", "volume": 5},
    "hobgoblin ii": {"type_id": 2456, "name": "Hobgoblin II", "slot": "drone", "volume": 5},
    "caldari navy antimatter charge s": {"type_id": 21898, "name": "Caldari Navy Antimatter Charge S", "slot": "charge", "volume": 0.0125},
    "nanite repair paste": {"type_id": 28668, "name": "Nanite Repair Paste", "slot": "cargo", "volume": 0.01},
}


class ParserTests(SimpleTestCase):
    def test_parse_header_items_charges_and_quantities(self):
        p = eft.parse(HARPY)
        self.assertEqual((p["hull"], p["name"]), ("Harpy", "Rail Harpy v3"))
        self.assertEqual(len(p["items"]), 17)  # 3 low + 4 mid + 4 high + 2 rigs + 1 drone line + 2 ammo + paste; the empty slot dropped
        gun = p["items"][7]
        self.assertEqual((gun["name"], gun["charge"], gun["quantity"]), ("150mm Railgun II", "Spike S", 1))
        self.assertEqual(p["items"][-3], {"name": "Spike S", "quantity": 1000, "charge": None})
        self.assertIn("Caldari Navy Antimatter Charge S", eft.names_in(p))
        self.assertEqual(eft.names_in(p)[0], "Harpy")

    def test_parse_errors(self):
        with self.assertRaises(eft.FittingError):
            eft.parse("")
        with self.assertRaises(eft.FittingError):
            eft.parse("Harpy\nDamage Control II")

    def test_layout_merges_identical_modules_and_keeps_slots_from_types(self):
        data = eft.layout(eft.parse(HARPY), TYPES)
        self.assertEqual(data["hull"]["type_id"], 11381)
        self.assertEqual(data["unknown"], [])
        lows = data["slots"]["low"]
        self.assertEqual([(r["name"], r["quantity"]) for r in lows], [("Magnetic Field Stabilizer II", 2), ("Damage Control II", 1)])
        highs = data["slots"]["high"]
        self.assertEqual(len(highs), 1)
        self.assertEqual((highs[0]["quantity"], highs[0]["charge"]["name"]), (4, "Spike S"))
        self.assertEqual([r["name"] for r in data["slots"]["rig"]], ["Small Core Defense Field Extender II", "Small Hybrid Collision Accelerator II"])
        self.assertEqual(data["slots"]["drone"][0]["quantity"], 2)
        self.assertEqual({r["name"]: r["quantity"] for r in data["slots"]["charge"]}, {"Spike S": 1000, "Caldari Navy Antimatter Charge S": 1000})
        self.assertEqual(data["slots"]["cargo"][0]["name"], "Nanite Repair Paste")

    def test_layout_reports_unknown_names(self):
        data = eft.layout(eft.parse("[Harpy, x]\nSomething Made Up\n150mm Railgun II, Made Up Ammo"), TYPES)
        self.assertEqual(data["unknown"], ["Made Up Ammo", "Something Made Up"])
        self.assertEqual(data["slots"]["high"][0]["charge"], None)

    def test_cost_adds_hull_fit_loaded_charges_drones_and_cargo(self):
        data = eft.layout(eft.parse(HARPY), TYPES)
        prices = {11381: 30e6, 10190: 1e6, 2048: 0.5e6, 5973: 0.2e6, 3831: 0.3e6, 2281: 0.4e6, 3244: 0.6e6,
                  3074: 0.8e6, 12814: 100.0, 31794: 1.2e6, 31524: 1.1e6, 2456: 0.3e6, 21898: 50.0, 28668: 1000.0}
        c = eft.cost(data, prices)
        self.assertAlmostEqual(c["hull"], 30e6)
        # fit: 2 MFS + DC + MWD + MSE + hardener + point + 4 guns + 4 loaded Spike + 2 rigs
        self.assertAlmostEqual(c["fit"], 2e6 + 0.5e6 + 0.2e6 + 0.3e6 + 0.4e6 + 0.6e6 + 4 * 0.8e6 + 4 * 100 + 1.2e6 + 1.1e6)
        self.assertAlmostEqual(c["drones"], 0.6e6)
        self.assertAlmostEqual(c["cargo"], 1000 * 100 + 1000 * 50 + 50 * 1000)
        self.assertAlmostEqual(c["total"], c["hull"] + c["fit"] + c["drones"] + c["cargo"])
        self.assertEqual(c["missing"], [])
        c2 = eft.cost(data, {k: v for k, v in prices.items() if k != 3074})
        self.assertEqual(c2["missing"], [3074])

    def test_text_export_round_trip(self):
        p = eft.parse(HARPY)
        text = eft.eft_text(p)
        self.assertTrue(text.startswith("[Harpy, Rail Harpy v3]\n"))
        self.assertIn("150mm Railgun II, Spike S", text)
        self.assertIn("Hobgoblin II x2", text)
        self.assertNotIn("[Empty High slot]", text)
        self.assertEqual(eft.parse(text)["items"], p["items"])


class SlotTests(SimpleTestCase):
    def test_slot_from_category_and_effects(self):
        self.assertEqual(types.slot_of({"category_id": 6}), "ship")
        self.assertEqual(types.slot_of({"category_id": 18}), "drone")
        self.assertEqual(types.slot_of({"category_id": 8}), "charge")
        self.assertEqual(types.slot_of({"category_id": 20}), "implant")
        self.assertEqual(types.slot_of({"category_id": 7, "dogma_effects": [{"effect_id": 11}]}), "low")
        self.assertEqual(types.slot_of({"category_id": 7, "dogma_effects": [{"effect_id": 13}]}), "mid")
        self.assertEqual(types.slot_of({"category_id": 7, "dogma_effects": [{"effect_id": 12}]}), "high")
        self.assertEqual(types.slot_of({"category_id": 7, "dogma_effects": [{"effect_id": 2663}]}), "rig")
        self.assertEqual(types.slot_of({"category_id": 32, "dogma_effects": [{"effect_id": 3772}]}), "subsystem")
        self.assertEqual(types.slot_of({"category_id": 4}), "cargo")


class IskAutoTests(SimpleTestCase):
    def test_decimals_by_size(self):
        self.assertEqual(isk_auto(1234), "1.23 k")
        self.assertEqual(isk_auto(12345), "12.3 k")
        self.assertEqual(isk_auto(120700), "121 k")
        self.assertEqual(isk_auto(2_512_300), "2.512 M")
        self.assertEqual(isk_auto(None), "–")


class KeyedTests(SimpleTestCase):
    def test_keyword_and_description_per_line(self):
        text = "King of the hill - Can hold a point\n- Sturdy – takes a beating\nShortsighted: struggles at range\nplain line\n\n"
        self.assertEqual(keyed(text), [
            ("King of the hill", "Can hold a point"), ("Sturdy", "takes a beating"),
            ("Shortsighted", "struggles at range"), ("", "plain line"),
        ])
