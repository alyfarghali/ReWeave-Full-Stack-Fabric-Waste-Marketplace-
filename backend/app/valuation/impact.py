"""Environmental impact of diverting textile scraps from landfill."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImpactFactors:
    # Rough sustainability factors used to estimate savings from diverting
    # textile waste from landfill. Candidates for per-fabric refinement.
    carbon_per_kg: float = 2.1  # kg CO2-equivalent saved per kg of fabric diverted
    water_per_kg: float = 2700.0  # liters of water saved per kg diverted (cotton-heavy estimate)
    energy_kwh_per_kg: float = 15.0  # production energy avoided per kg diverted

    # "Equivalencies" that translate raw CO2/water totals into relatable
    # everyday comparisons for the impact dashboard.
    co2_kg_per_car_mile: float = 0.39  # average passenger car (EPA)
    co2_kg_per_phone_charge: float = 0.0084  # one full smartphone charge
    water_l_per_plastic_bottle: float = 0.5  # standard disposable bottle
    water_l_per_shower: float = 65.0  # average 8-minute shower


@dataclass(frozen=True)
class Equivalents:
    car_miles: float
    phone_charges: int
    plastic_bottles: int
    showers: float

    def as_dict(self) -> dict:
        return {
            "car_miles": self.car_miles,
            "phone_charges": self.phone_charges,
            "plastic_bottles": self.plastic_bottles,
            "showers": self.showers,
        }


class ImpactCalculator:
    def __init__(self, factors: ImpactFactors | None = None):
        self.factors = factors or ImpactFactors()

    def carbon_saved_kg(self, weight_kg: float) -> float:
        return round(weight_kg * self.factors.carbon_per_kg, 2)

    def water_saved_l(self, weight_kg: float) -> float:
        return round(weight_kg * self.factors.water_per_kg, 2)

    def raw_carbon_kg(self, weight_kg: float) -> float:
        """Unrounded CO2 for intermediate math (e.g. destination scoring)."""
        return weight_kg * self.factors.carbon_per_kg

    def raw_water_l(self, weight_kg: float) -> float:
        return weight_kg * self.factors.water_per_kg

    def energy_saved_kwh(self, weight_kg: float) -> float:
        return round(weight_kg * self.factors.energy_kwh_per_kg, 2)

    def equivalents(self, carbon_kg: float, water_l: float) -> Equivalents:
        f = self.factors
        return Equivalents(
            car_miles=round(carbon_kg / f.co2_kg_per_car_mile, 1),
            phone_charges=round(carbon_kg / f.co2_kg_per_phone_charge),
            plastic_bottles=round(water_l / f.water_l_per_plastic_bottle),
            showers=round(water_l / f.water_l_per_shower, 1),
        )


impact_calculator = ImpactCalculator()
