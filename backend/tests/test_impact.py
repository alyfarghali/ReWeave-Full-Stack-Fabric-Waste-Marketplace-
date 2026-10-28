import unittest

from support import ApiHarness  # noqa: F401  (puts the app on sys.path)

from app.admin.metrics import AdminMetricsReport
from app.marketplace.models import Lot
from app.valuation import impact_calculator


class ImpactTests(unittest.TestCase):
    def test_equivalents_follow_impact_factors(self):
        f = impact_calculator.factors
        eq = impact_calculator.equivalents(f.co2_kg_per_car_mile * 10, f.water_l_per_shower * 4)

        self.assertEqual(eq.car_miles, 10.0)
        self.assertEqual(eq.showers, 4.0)

    def test_admin_dashboard_impact_comes_from_calculator(self):
        weight = 3.0
        lot = Lot(
            name="Blue cotton",
            fabric_type="cotton",
            status="available",
            weight_kg=weight,
            carbon_saved_kg=impact_calculator.carbon_saved_kg(weight),
            water_saved_l=impact_calculator.water_saved_l(weight),
        )

        impact = AdminMetricsReport([lot], []).impact()

        eq = impact_calculator.equivalents(lot.carbon_saved_kg, lot.water_saved_l)
        self.assertEqual(impact["carbon_equiv_car_miles"], eq.car_miles)
        self.assertEqual(impact["carbon_equiv_phones"], eq.phone_charges)
        self.assertEqual(impact["water_equiv_showers"], eq.showers)
        self.assertEqual(impact["water_equiv_bottles"], eq.plastic_bottles)
        self.assertEqual(impact["energy_saved_kwh"], impact_calculator.energy_saved_kwh(weight))


if __name__ == "__main__":
    unittest.main()
