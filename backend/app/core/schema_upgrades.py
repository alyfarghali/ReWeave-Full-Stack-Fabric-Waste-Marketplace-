"""In-place column upgrades for databases created by older versions of the app.

There is no migration tool; on startup we compare each table's live columns
against what the models expect and ``ALTER TABLE ... ADD COLUMN`` anything
missing. Works on both SQLite (local dev) and Postgres (Supabase).
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


class SchemaUpgrader:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.is_postgres = engine.dialect.name == "postgresql"

    def run(self) -> None:
        self._upgrade_lots()
        self._upgrade_scan_runs()
        self._upgrade_users()

    # -- per-table upgrades ---------------------------------------------------

    def _upgrade_lots(self) -> None:
        """Keep older local dev databases compatible with the current Lot model."""
        has_scan_runs = inspect(self.engine).has_table("scan_runs")
        if self.is_postgres and has_scan_runs:
            scan_run_fk = "INTEGER REFERENCES scan_runs(id) ON DELETE SET NULL"
        else:
            scan_run_fk = "INTEGER"
        self._add_missing_columns(
            "lots",
            {
                "lot_key": "VARCHAR",
                "scan_run_id": scan_run_fk,
                "piece_images": self._json_column("'[]'"),
                "origin_lat": "FLOAT",
                "origin_lng": "FLOAT",
            },
        )

    def _upgrade_scan_runs(self) -> None:
        self._add_missing_columns(
            "scan_runs",
            {
                "annotated_image_data_url": "TEXT",
                "image_width": "INTEGER DEFAULT 0",
                "image_height": "INTEGER DEFAULT 0",
                "piece_count": "INTEGER DEFAULT 0",
                "group_count": "INTEGER DEFAULT 0",
                "total_weight_kg": "FLOAT DEFAULT 0",
                "total_carbon_saved_kg": "FLOAT DEFAULT 0",
                "total_water_saved_l": "FLOAT DEFAULT 0",
                "created_at": "TIMESTAMP",
                "summary": self._json_column("'{}'"),
            },
        )

    def _upgrade_users(self) -> None:
        """Buyer location columns, added after the managed Supabase users table."""
        self._add_missing_columns("users", {"lat": "FLOAT", "lng": "FLOAT"})

    # -- helpers ----------------------------------------------------------------

    def _json_column(self, empty_literal: str) -> str:
        if self.is_postgres:
            return f"JSONB DEFAULT {empty_literal}::jsonb"
        return f"JSON DEFAULT {empty_literal}"

    def _add_missing_columns(self, table: str, expected: dict[str, str]) -> None:
        inspector = inspect(self.engine)
        if not inspector.has_table(table):
            return
        existing = {col["name"] for col in inspector.get_columns(table)}
        statements = [
            f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"
            for name, sql_type in expected.items()
            if name not in existing
        ]
        if not statements:
            return
        with self.engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
