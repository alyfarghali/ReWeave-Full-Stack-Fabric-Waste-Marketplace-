"""Reuse pathways available for each broad fabric category."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pathway:
    name: str
    revenue_multiplier: float  # x base $/kg price
    co2_multiplier: float  # x carbon saved by diverting from landfill

    @property
    def is_landfill(self) -> bool:
        return self.revenue_multiplier == 0 and self.co2_multiplier == 0


LANDFILL = Pathway("Landfill Disposal", 0.0, 0.0)

CATEGORY_KEYWORDS = {
    "denim_cotton": ["denim", "cotton", "twill", "jersey", "linen"],
    "synthetic": ["polyester", "nylon", "spandex"],
    "wool_silk": ["wool", "silk"],
}

PATHWAYS: dict[str, list[Pathway]] = {
    "denim_cotton": [
        Pathway("Upcycling — Tote Bags & Accessories", 1.5, 1.3),
        Pathway("Fiber Reclamation", 1.2, 1.0),
        Pathway("Insulation Manufacturing", 1.0, 0.7),
        Pathway("Industrial Wiping Cloths", 0.8, 0.5),
        LANDFILL,
    ],
    "synthetic": [
        Pathway("Insulation Manufacturing", 1.2, 0.8),
        Pathway("Fiber Reclamation", 1.0, 1.0),
        Pathway("Industrial Wiping Cloths", 0.8, 0.5),
        LANDFILL,
    ],
    "wool_silk": [
        Pathway("Upcycling — Apparel Accessories", 1.6, 1.3),
        Pathway("Fiber Reclamation", 1.1, 1.0),
        Pathway("Insulation Manufacturing", 0.9, 0.7),
        LANDFILL,
    ],
    "general": [
        Pathway("Fiber Reclamation", 1.1, 1.0),
        Pathway("Industrial Wiping Cloths", 0.9, 0.6),
        Pathway("Insulation Manufacturing", 0.8, 0.6),
        LANDFILL,
    ],
}


def pathways_for(fabric_type: str) -> list[Pathway]:
    fabric_lower = (fabric_type or "").lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in fabric_lower for keyword in keywords):
            return PATHWAYS[category]
    return PATHWAYS["general"]
