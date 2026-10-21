"""Lot endpoints: list scans as inventory, browse it, claim lots, manage listings."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth.dependencies import require_admin, require_operator, require_purchaser
from ..auth.models import Role, User
from ..core.database import get_db
from .repository import LotRepository
from .schemas import LotClaim, LotOut, LotSearch, ScanListingOut, ScanListingRequest
from .service import LotNotFound, LotService, LotStateError

router = APIRouter(prefix="/api/lots", tags=["lots"])


def get_lot_service(db: Session = Depends(get_db)) -> LotService:
    return LotService(db)


def _run(action):
    """Translate lot domain errors into HTTP errors."""
    try:
        return action()
    except LotNotFound:
        raise HTTPException(status_code=404, detail="Lot not found")
    except LotStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[LotOut])
def list_lots(criteria: LotSearch = Depends(), db: Session = Depends(get_db)):
    return [LotOut.from_lot(lot) for lot in LotRepository(db).search(criteria)]


@router.post("/from-scan", response_model=ScanListingOut, dependencies=[Depends(require_operator)])
def list_scan(body: ScanListingRequest, lots: LotService = Depends(get_lot_service)):
    """Record a scan run and list each of its sort bins as a lot in one call."""
    return lots.list_scan(body.scan.model_dump(), body.origin_lat, body.origin_lng)


@router.post("/{lot_id}/claim", response_model=LotOut)
def claim_lot(
    lot_id: int,
    claim: LotClaim,
    user: User = Depends(require_purchaser),
    lots: LotService = Depends(get_lot_service),
):
    # Buyers always claim as themselves; only an admin may assign a lot to a named buyer.
    buyer_name = (claim.buyer_name or user.name) if user.role == Role.ADMIN else user.name
    return LotOut.from_lot(_run(lambda: lots.claim(lot_id, buyer_name, claim.quantity_kg)))


@router.patch("/{lot_id}/delist", response_model=LotOut, dependencies=[Depends(require_admin)])
def delist_lot(lot_id: int, lots: LotService = Depends(get_lot_service)):
    return LotOut.from_lot(_run(lambda: lots.delist(lot_id)))


@router.patch("/{lot_id}/relist", response_model=LotOut, dependencies=[Depends(require_admin)])
def relist_lot(lot_id: int, lots: LotService = Depends(get_lot_service)):
    return LotOut.from_lot(_run(lambda: lots.relist(lot_id)))


@router.delete("/{lot_id}", dependencies=[Depends(require_admin)])
def delete_lot(lot_id: int, lots: LotService = Depends(get_lot_service)):
    _run(lambda: lots.delete(lot_id))
    return {"status": "ok", "deleted_lot_id": lot_id}
