"""Template filters: ISK formatting rules."""
from django.test import SimpleTestCase

from ..templatetags.shipyard_tags import isk, isk_auto


class IskTests(SimpleTestCase):
    def test_isk_digits(self):
        self.assertEqual(isk(153_910, 0), "154 k")
        self.assertEqual(isk(153_910, 2), "153.91 k")
        self.assertEqual(isk(92_683_787, 1), "92.7 M")
        self.assertEqual(isk(None), "–")

    def test_isk_auto_follows_the_owners_rule(self):
        # two decimals under 10 k, one from 10 k, none from 100 k
        self.assertEqual(isk_auto(1_234.5), "1.23 k")
        self.assertEqual(isk_auto(9_999), "10.00 k")
        self.assertEqual(isk_auto(12_345), "12.3 k")
        self.assertEqual(isk_auto(99_950), "100.0 k")
        self.assertEqual(isk_auto(153_910), "154 k")
        self.assertEqual(isk_auto(2_345_678), "2.346 M")  # millions keep their thousands
        self.assertEqual(isk_auto(512), "512.00")
        self.assertEqual(isk_auto(None), "–")
