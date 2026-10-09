"""Buy orders from nearby systems that reach Jita 4-4."""
from django.test import SimpleTestCase

from ..services.nearbuy import effective_buy_max, reaches

JITA, PERIMETER, MAURASI = 30000142, 30000144, 30000140
STATION = 60003760
NEAR = {JITA: 0, PERIMETER: 1}


def order(price, system, location=0, rng="station", remain=10):
    return {"price": price, "system_id": system, "location_id": location, "range": rng, "volume_remain": remain}


class ReachTests(SimpleTestCase):
    def test_rules(self):
        self.assertTrue(reaches(order(1, JITA, STATION, "station"), STATION, NEAR))       # at the station
        self.assertFalse(reaches(order(1, JITA, 60000001, "station"), STATION, NEAR))     # another Jita station, station range
        self.assertTrue(reaches(order(1, JITA, 60000001, "solarsystem"), STATION, NEAR))  # anywhere in Jita
        self.assertTrue(reaches(order(1, JITA, 60000001, "2"), STATION, NEAR))
        self.assertTrue(reaches(order(1, PERIMETER, 60000002, "1"), STATION, NEAR))       # Perimeter, one jump: the owner's case
        self.assertTrue(reaches(order(1, PERIMETER, 60000002, "5"), STATION, NEAR))
        self.assertTrue(reaches(order(1, PERIMETER, 60000002, "region"), STATION, NEAR))
        self.assertFalse(reaches(order(1, PERIMETER, 60000002, "station"), STATION, NEAR))
        self.assertFalse(reaches(order(1, PERIMETER, 60000002, "solarsystem"), STATION, NEAR))
        self.assertTrue(reaches(order(1, MAURASI, 60000003, "region"), STATION, NEAR))    # region-wide from anywhere
        self.assertFalse(reaches(order(1, MAURASI, 60000003, "10"), STATION, NEAR))       # not a listed system

    def test_effective_max(self):
        orders = [order(100, JITA, STATION), order(130, PERIMETER, 60000002, "1"), order(200, PERIMETER, 60000002, "station"),
                  order(150, MAURASI, 60000003, "40"), order(300, PERIMETER, 60000002, "1", remain=0)]
        self.assertEqual(effective_buy_max(orders, STATION, NEAR), 130.0)
        self.assertIsNone(effective_buy_max([order(200, PERIMETER, 60000002, "station")], STATION, NEAR))
