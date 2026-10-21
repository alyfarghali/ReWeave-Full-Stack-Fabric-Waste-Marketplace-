"""Admin operations dashboard and inventory reset endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth.dependencies import require_admin, require_operator
from ..core.database import get_db
from ..marketplace.repository import LotRepository, ScanRunRepository
from ..marketplace.service import LotService
from .metrics import AdminMetricsReport

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/metrics", dependencies=[Depends(require_admin)])
def get_metrics(db: Session = Depends(get_db)):
    lots = LotRepository(db).all(newest_first=True)
    scan_runs = ScanRunRepository(db).all(newest_first=True)
    return AdminMetricsReport(lots, scan_runs).build()


@router.post("/reset-demo", dependencies=[Depends(require_operator)])
def reset_demo(db: Session = Depends(get_db)):
    """Wipe scanned inventory and scan summaries; logins and buyer profiles are kept."""
    return {"status": "ok", **LotService(db).reset()}
