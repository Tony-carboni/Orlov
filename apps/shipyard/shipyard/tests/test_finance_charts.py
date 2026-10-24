"""The Finance tab's donut (0.33.0): pure geometry from the sheet's groups."""
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
