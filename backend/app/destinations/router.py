"""AI Material Destination Engine endpoint -- recommends reuse pathways,
buyers, and environmental impact for a detected fabric group.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth.dependencies import require_operator
from ..core.config import get_settings
from ..core.database import get_db
from ..core.openrouter import OpenRouterClient
from .engine import BuyerMatcher, DestinationEngine, PathwayNamer
from .schemas import DestinationAnalysis, DestinationAnalysisRequest

router = APIRouter(prefix="/api/destinations", tags=["destinations"])


def get_engine(db: Session = Depends(get_db)) -> DestinationEngine:
    settings = get_settings()
    client = OpenRouterClient(settings.openrouter_api_key, app_title="Reweave Destination Engine")
    model = settings.openrouter_vision_models[0] if settings.openrouter_vision_models else "openai/gpt-4o-mini"
    return DestinationEngine(buyers=BuyerMatcher(db), namer=PathwayNamer(client, model))


@router.post("/analyze", response_model=DestinationAnalysis, dependencies=[Depends(require_operator)])
def analyze(req: DestinationAnalysisRequest, engine: DestinationEngine = Depends(get_engine)):
    return engine.analyze(req)
