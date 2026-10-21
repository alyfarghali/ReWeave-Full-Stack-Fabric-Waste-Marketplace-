"""Queries over lots and scan runs. No business rules live here."""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .models import Lot, ScanRun
from .schemas import LotSearch

SEARCHABLE_COLUMNS = (Lot.name, Lot.fabric_type, Lot.color_name, Lot.composition, Lot.description)


class LotRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, lot_id: int) -> Lot | None:
        return self.db.get(Lot, lot_id)

    def get_for_update(self, lot_id: int) -> Lot | None:
        """Row-locked read so two concurrent claims cannot both take the same weight."""
        return self.db.query(Lot).filter(Lot.id == lot_id).with_for_update().first()

    def all(self, newest_first: bool = False) -> list[Lot]:
        query = self.db.query(Lot)
        if newest_first:
            query = query.order_by(Lot.created_at.desc())
        return query.all()

    def add(self, lot: Lot) -> None:
        self.db.add(lot)

    def delete(self, lot: Lot) -> None:
        self.db.delete(lot)

    def search(self, criteria: LotSearch) -> list[Lot]:
        query = self.db.query(Lot)
        if criteria.status:
            query = query.filter(Lot.status == criteria.status)
        if criteria.fabric_type:
            query = query.filter(Lot.fabric_type == criteria.fabric_type)
        if criteria.color_name:
            query = query.filter(Lot.color_name == criteria.color_name)
        if criteria.claimed_by:
            query = query.filter(Lot.claimed_by == criteria.claimed_by)
        if criteria.min_price is not None:
            query = query.filter(Lot.price_usd >= criteria.min_price)
        if criteria.max_price is not None:
            query = query.filter(Lot.price_usd <= criteria.max_price)
        if criteria.q and criteria.q.strip():
            query = query.filter(self._text_match(criteria.q.strip()))
        return query.order_by(Lot.created_at.desc()).all()

    def _text_match(self, term: str):
        """Postgres full-text search; substring match on SQLite."""
        if self.db.get_bind().dialect.name == "postgresql":
            document = func.to_tsvector(
                "english",
                func.concat_ws(" ", *(func.coalesce(column, "") for column in SEARCHABLE_COLUMNS)),
            )
            return document.op("@@")(func.websearch_to_tsquery("english", term))
        pattern = f"%{term}%"
        return or_(*(column.ilike(pattern) for column in SEARCHABLE_COLUMNS))


class ScanRunRepository:
    def __init__(self, db: Session):
        self.db = db

    def all(self, newest_first: bool = False) -> list[ScanRun]:
        query = self.db.query(ScanRun)
        if newest_first:
            query = query.order_by(ScanRun.created_at.desc())
        return query.all()

    def add(self, scan: ScanRun) -> None:
        self.db.add(scan)
