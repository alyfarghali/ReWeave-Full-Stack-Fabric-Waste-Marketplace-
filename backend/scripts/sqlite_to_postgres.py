"""Copy every table from a SQLite database into Postgres, keeping row ids.

Run once when moving an existing local database to Postgres. Start the
Postgres container first (`docker compose up -d db`), but don't start the API
against it yet, or its startup seed will fill the tables:

    python scripts/sqlite_to_postgres.py sqlite:///./scraps.db \
        postgresql://reweave:reweave@localhost:5433/reweave

The target must be empty unless --replace is given, which truncates it first.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base  # noqa: E402
from app.core.schema_upgrades import SchemaUpgrader  # noqa: E402

# Importing the models registers every table on Base.metadata.
import app.auth.models  # noqa: E402,F401
import app.destinations.models  # noqa: E402,F401
import app.marketplace.models  # noqa: E402,F401

BATCH_SIZE = 200


def row_counts(engine) -> dict[str, int]:
    with engine.connect() as conn:
        return {table.name: conn.scalar(select(func.count()).select_from(table)) for table in Base.metadata.sorted_tables}


def copy_table(table, source, target) -> int:
    # Older SQLite files may predate some columns; copy only the ones they have.
    source_columns = {col["name"] for col in inspect(source).get_columns(table.name)}
    columns = [col for col in table.columns if col.name in source_columns]
    copied = 0
    with source.connect() as src, target.begin() as dst:
        result = src.execute(select(*columns).order_by(table.primary_key.columns.values()[0]))
        while batch := result.fetchmany(BATCH_SIZE):
            dst.execute(table.insert(), [dict(row._mapping) for row in batch])
            copied += len(batch)
    return copied


def reset_sequence(table, target) -> None:
    """Point the id sequence past the copied ids so new rows don't collide."""
    with target.begin() as conn:
        conn.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"
            )
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sqlite_url")
    parser.add_argument("postgres_url")
    parser.add_argument("--replace", action="store_true", help="truncate the target tables first")
    args = parser.parse_args()

    source = create_engine(args.sqlite_url)
    target = create_engine(args.postgres_url)
    if target.dialect.name != "postgresql":
        sys.exit("The target must be a postgresql:// URL.")

    Base.metadata.create_all(bind=target)
    SchemaUpgrader(target).run()

    existing = {name: n for name, n in row_counts(target).items() if n}
    if existing and not args.replace:
        sys.exit(f"Target already has rows ({existing}). Re-run with --replace to overwrite them.")
    if args.replace:
        names = ", ".join(table.name for table in Base.metadata.sorted_tables)
        with target.begin() as conn:
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))

    for table in Base.metadata.sorted_tables:
        if not inspect(source).has_table(table.name):
            print(f"{table.name}: not in source, skipped")
            continue
        copied = copy_table(table, source, target)
        reset_sequence(table, target)
        print(f"{table.name}: {copied} rows")

    source_counts, target_counts = row_counts(source), row_counts(target)
    mismatched = {name: (source_counts[name], target_counts[name]) for name in source_counts if source_counts[name] != target_counts[name]}
    if mismatched:
        sys.exit(f"Row counts differ (source, target): {mismatched}")
    print("Row counts match.")


if __name__ == "__main__":
    main()
