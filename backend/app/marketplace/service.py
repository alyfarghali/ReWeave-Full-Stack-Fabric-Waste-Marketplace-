"""Marketplace use cases: list a scan's bins as lots, claim them, manage listings."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Lot, LotStateError, ScanRun
from .piece_images import PieceImages
from .repository import LotRepository, ScanRunRepository
from .scan_listing import ScanListing
from .schemas import BinListing, LotCreate, ScanListingOut, ScanRunCreate


class LotNotFound(Exception):
    pass


class LotService:
    def __init__(self, db: Session):
        self.db = db
        self.lots = LotRepository(db)
        self.scan_runs = ScanRunRepository(db)

    # -- listing ---------------------------------------------------------------------

    def list_scan(
        self, scan: dict, origin_lat: float | None = None, origin_lng: float | None = None
    ) -> ScanListingOut:
        """Record a scan run and list every sort bin from it as a lot, in one transaction."""
        listing = ScanListing(scan)
        run = self._new_scan_run(listing.scan_run())
        self.scan_runs.add(run)
        self.db.flush()  # assigns run.id for the lots' foreign key

        listed = []
        for bin_id, payload in listing.lots(run.id, origin_lat, origin_lng):
            lot = self._new_lot(payload)
            self.lots.add(lot)
            listed.append((bin_id, lot))
        self.db.commit()

        instructions = {group.get("sort_group_id"): group.get("sort_instruction") for group in listing.groups}
        return ScanListingOut(
            scan_run_id=run.id,
            bins=[
                BinListing(
                    sort_group_id=bin_id,
                    lot_id=lot.id,
                    name=lot.name,
                    piece_count=lot.piece_count,
                    weight_kg=lot.weight_kg,
                    price_usd=lot.price_usd,
                    sort_instruction=instructions.get(bin_id),
                )
                for bin_id, lot in listed
            ],
            total_weight_kg=run.total_weight_kg,
            total_carbon_saved_kg=run.total_carbon_saved_kg,
            total_water_saved_l=run.total_water_saved_l,
            warnings=list(scan.get("warnings") or []),
        )

    # -- lifecycle -------------------------------------------------------------------

    def claim(self, lot_id: int, buyer_name: str, quantity_kg: float | None) -> Lot:
        lot = self.lots.get_for_update(lot_id)
        if not lot:
            raise LotNotFound
        claimed = lot.claim(buyer_name, quantity_kg)
        if claimed is not lot:
            self.lots.add(claimed)
        return self._save(claimed)

    def delist(self, lot_id: int) -> Lot:
        lot = self._get(lot_id)
        lot.delist()
        return self._save(lot)

    def relist(self, lot_id: int) -> Lot:
        lot = self._get(lot_id)
        lot.relist()
        return self._save(lot)

    def delete(self, lot_id: int) -> None:
        self.lots.delete(self._get(lot_id))
        self.db.commit()

    def reset(self) -> dict:
        """Wipe scanned inventory and scan summaries (users and buyers are kept)."""
        deleted_lots = self.db.query(Lot).delete()
        deleted_runs = self.db.query(ScanRun).delete()
        self.db.commit()
        try:
            if self.db.get_bind().dialect.name == "postgresql":
                self.db.execute(text("ALTER TABLE public.lots ALTER COLUMN id RESTART WITH 1"))
                self.db.execute(text("ALTER TABLE public.scan_runs ALTER COLUMN id RESTART WITH 1"))
                self.db.commit()
        except Exception:
            self.db.rollback()
        return {"deleted_lots": deleted_lots, "deleted_scan_runs": deleted_runs}

    # -- helpers ---------------------------------------------------------------------

    def _get(self, lot_id: int) -> Lot:
        lot = self.lots.get(lot_id)
        if not lot:
            raise LotNotFound
        return lot

    @staticmethod
    def _new_lot(incoming: LotCreate) -> Lot:
        data = incoming.model_dump()
        data["lot_key"] = incoming.lot_key or Lot.make_key(incoming.fabric_type, incoming.composition, incoming.color_name)
        data["piece_images"] = PieceImages.normalize(data.get("piece_images"))
        lot = Lot(**data)
        if lot.price_usd <= 0:
            lot.reprice()
        lot.recompute_impact()
        return lot

    @staticmethod
    def _new_scan_run(scan: ScanRunCreate) -> ScanRun:
        return ScanRun(**scan.model_dump())

    def _save(self, entity):
        self.db.commit()
        self.db.refresh(entity)
        return entity


__all__ = ["LotNotFound", "LotService", "LotStateError"]
