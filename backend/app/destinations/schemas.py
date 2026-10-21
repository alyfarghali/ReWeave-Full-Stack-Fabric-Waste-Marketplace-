from typing import List, Optional

from pydantic import BaseModel


class ImpactEquivalents(BaseModel):
    car_miles: float
    phone_charges: int
    plastic_bottles: int
    showers: float


class DestinationOption(BaseModel):
    name: str
    revenue_usd: float
    co2_saved_kg: float
    score: int


class BuyerMatch(BaseModel):
    name: str
    match_pct: int


class DestinationAnalysisRequest(BaseModel):
    fabric_type: str
    composition: str = ""
    color_name: str = ""
    weight_kg: float
    material_family: Optional[str] = None


class DestinationAnalysis(BaseModel):
    recommended: DestinationOption
    alternatives: List[DestinationOption]
    recommended_buyers: List[BuyerMatch]
    sale_probability_pct: int
    expected_days_to_sale: float
    environmental_equivalents: ImpactEquivalents
    landfill_co2_saved_kg: float
