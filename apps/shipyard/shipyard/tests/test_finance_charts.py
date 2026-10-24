"""The Finance tab's donut and waterfall (0.33.0): pure geometry from the sheet's groups."""
from django.test import SimpleTestCase

from ..services import finance_charts as fc

M = 1e6


class ChartTests(SimpleTestCase):
    def test_donut_segments_cover_the_ring_in_order(self):
        groups = [{"key": "cash", "label": "Liquid ISK", "total": 3216.3 * M}, {"key": "pool", "label": "Reward ISK", "total": 2247.8 * M},
                  {"key": "held", "label": "Goods held", "total": 460.0 * M}, {"key": "lp", "label": "Loyalty points", "total": 0.0}]
        d = fc.donut(groups)
        self.assertAlmostEqual(d["total"], 5924.1 * M)
        self.assertEqual([s["key"] for s in d["segments"]], ["cash", "pool", "held"])  # the empty one is left out
        self.assertAlmostEqual(sum(s["pct"] for s in d["segments"]), 100.0)
        self.assertEqual(d["segments"][0]["offset"], "25.00")  # the first segment starts at the top
        self.assertAlmostEqual(float(d["segments"][1]["offset"]), 25 - d["segments"][0]["pct"], places=2)
        self.assertAlmostEqual(d["segments"][0]["start"], 90.0)
        self.assertAlmostEqual(d["segments"][-1]["end"], -270.0, places=1)
        self.assertEqual(d["segments"][2]["colour"], "#ffd75e")
        self.assertEqual(fc.donut([]), {"total": 0.0, "segments": []})

    def test_waterfall_walks_from_the_opening_to_the_result(self):
        groups = [{"key": "project_sales", "label": "Project buyback sales", "total": 1143.3 * M},
                  {"key": "project_rewards", "label": "Rewards", "total": -294.4 * M},
                  {"key": "gap", "label": "Not explained", "total": 0.0},
                  {"key": "structure", "label": "Structure income", "total": 136.9 * M}]
        w = fc.waterfall(groups)
        self.assertEqual([b["key"] for b in w["bars"]], ["project_sales", "project_rewards", "structure", "result"])
        self.assertAlmostEqual(w["result"], 985.8 * M)
        self.assertEqual(w["bars"][-1]["text"], "986")
        self.assertEqual(w["bars"][1]["text"], "-294")
        self.assertEqual(w["bars"][1]["kind"], "neg")
        # the rewards bar hangs from the level the sales reached; the result bar stands on zero and reaches the same top as the running level
        sales, rewards, result = w["bars"][0], w["bars"][1], w["bars"][-1]
        self.assertAlmostEqual(rewards["y"], sales["y"], places=0)
        self.assertAlmostEqual(result["y"] + result["h"], w["zero"], places=0)
        self.assertTrue(all(b["x"] >= 10 and b["x"] + b["w"] <= 420 for b in w["bars"]))
        self.assertEqual(w["floor"], 150.0)
        # an opening adds a grey first bar and shifts the result
        w2 = fc.waterfall(groups, opening=200 * M)
        self.assertEqual(w2["bars"][0]["kind"], "opening")
        self.assertAlmostEqual(w2["result"], 1185.8 * M)
        # a fall below zero keeps every bar inside the drawing
        w3 = fc.waterfall([{"key": "transfers", "label": "T", "total": -500 * M}])
        self.assertTrue(all(b["y"] >= 0 and b["y"] + b["h"] <= w3["floor"] + 0.01 for b in w3["bars"]))
        self.assertLess(w3["zero"], w3["floor"])
