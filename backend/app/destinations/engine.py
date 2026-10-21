"""AI Material Destination Engine.

Given a detected fabric group (fabric type, composition, color, weight), score
candidate reuse pathways (upcycling, fiber reclamation, insulation, landfill,
etc.), match interested buyers, and translate the environmental payoff into
everyday equivalents. Pure analysis layer -- no DB writes, no lot changes.

Scoring formula: 40% revenue + 30% CO2 saved + 20% demand + 10% speed-to-sale,
each normalized to 0-100. Demand/speed are derived from buyer-interest overlap
so the math stays deterministic even without an LLM available.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..core.openrouter import OpenRouterClient, OpenRouterError
from ..valuation import ImpactCalculator, PricingModel, impact_calculator, pricing_model
from .models import Buyer
from .catalog import Pathway, pathways_for
from .schemas import BuyerMatch, DestinationAnalysis, DestinationAnalysisRequest, DestinationOption, ImpactEquivalents


class BuyerMatcher:
    """Ranks buyers by how many of a group's material keywords they want."""

    MAX_MATCHES = 3

    def __init__(self, db: Session):
        self.db = db

    def match(self, fabric_type: str, material_family: str | None, color_name: str) -> tuple[list[BuyerMatch], int]:
        """Return the top buyer matches and a 0-100 demand score."""
        keywords = {k.lower() for k in (fabric_type, material_family, color_name) if k}
        scored = []
        for buyer in self.db.query(Buyer).all():
            overlap = buyer.material_overlap(keywords)
            if overlap:
                scored.append((min(99, 70 + overlap * 15), buyer.name))
        scored.sort(key=lambda item: item[0], reverse=True)
        matches = [BuyerMatch(name=name, match_pct=pct) for pct, name in scored[: self.MAX_MATCHES]]
        return matches, min(100, len(scored) * 33)


class PathwayNamer:
    """Optional LLM flavor text: rewrites generic pathway names for a specific
    fabric. Returns None (keep generic names) whenever the LLM is unavailable."""

    def __init__(self, client: OpenRouterClient, model: str):
        self.client = client
        self.model = model

    def rename(self, fabric_type: str, material_family: str | None, names: list[str]) -> list[str] | None:
        if not self.client.configured:
            return None
        prompt = (
            "Rewrite each reuse pathway name below into a short (3-6 word), specific, "
            f"marketable name for scrap fabric of type '{fabric_type}' "
            f"(material family: '{material_family or 'unknown'}'). "
            "Keep the same order and meaning -- do not reorder or merge entries. "
            "Return JSON only: {\"names\": [\"...\", ...]}. Pathways: " + json.dumps(names)
        )
        try:
            data = self.client.complete_json(
                self.model,
                [{"role": "user", "content": prompt}],
                timeout_s=20,
                temperature=0.4,
                max_tokens=300,
            )
            result = data.get("names")
        except (OpenRouterError, AttributeError, json.JSONDecodeError):
            return None
        if isinstance(result, list) and len(result) == len(names):
            return [str(n) for n in result]
        return None


class DestinationEngine:
    WEIGHT_REVENUE = 0.4
    WEIGHT_CO2 = 0.3
    WEIGHT_DEMAND = 0.2
    WEIGHT_SPEED = 0.1

    def __init__(
        self,
        buyers: BuyerMatcher,
        namer: PathwayNamer,
        pricing: PricingModel = pricing_model,
        impact: ImpactCalculator = impact_calculator,
    ):
        self.buyers = buyers
        self.namer = namer
        self.pricing = pricing
        self.impact = impact

    def analyze(self, req: DestinationAnalysisRequest, piece_count: int = 20) -> DestinationAnalysis:
        catalog = pathways_for(req.fabric_type)
        base_price = self.pricing.base_price(
            fabric_type=req.fabric_type or "mixed textile",
            composition=req.composition or "",
            color_name=req.color_name or "",
            weight_kg=req.weight_kg,
            piece_count=piece_count,
        )
        base_co2 = self.impact.raw_carbon_kg(req.weight_kg)

        recommended_buyers, demand_score = self.buyers.match(req.fabric_type, req.material_family, req.color_name)
        names = self.namer.rename(req.fabric_type, req.material_family, [p.name for p in catalog])

        options = self._score(catalog, base_price, base_co2, demand_score, names)
        recommended, *alternatives = sorted(options, key=lambda o: o.score, reverse=True)

        co2_ratio = recommended.co2_saved_kg / base_co2 if base_co2 else 0.0
        water_saved_l = self.impact.raw_water_l(req.weight_kg) * co2_ratio
        equivalents = self.impact.equivalents(recommended.co2_saved_kg, water_saved_l)

        landfill_co2 = next((round(base_co2 * p.co2_multiplier, 2) for p in catalog if p.is_landfill), 0.0)

        return DestinationAnalysis(
            recommended=recommended,
            alternatives=alternatives,
            recommended_buyers=recommended_buyers,
            sale_probability_pct=min(98, 60 + round(demand_score * 0.35)),
            expected_days_to_sale=round(1 + (100 - demand_score) / 100 * 6, 1),
            environmental_equivalents=ImpactEquivalents(**equivalents.as_dict()),
            landfill_co2_saved_kg=landfill_co2,
        )

    def _score(
        self,
        catalog: list[Pathway],
        base_price: float,
        base_co2: float,
        demand_score: int,
        names: list[str] | None,
    ) -> list[DestinationOption]:
        revenues = [round(base_price * p.revenue_multiplier, 2) for p in catalog]
        co2s = [round(base_co2 * p.co2_multiplier, 2) for p in catalog]
        max_revenue = max(revenues) or 1.0
        max_co2 = max(co2s) or 1.0

        options = []
        for idx, pathway in enumerate(catalog):
            demand = 0 if pathway.is_landfill else demand_score
            score = round(
                self.WEIGHT_REVENUE * (revenues[idx] / max_revenue * 100)
                + self.WEIGHT_CO2 * (co2s[idx] / max_co2 * 100)
                + self.WEIGHT_DEMAND * demand
                + self.WEIGHT_SPEED * demand
            )
            options.append(
                DestinationOption(
                    name=names[idx] if names else pathway.name,
                    revenue_usd=revenues[idx],
                    co2_saved_kg=co2s[idx],
                    score=score,
                )
            )
        return options
