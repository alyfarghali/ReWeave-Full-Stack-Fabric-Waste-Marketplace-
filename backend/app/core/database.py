"""Database connection.

The app runs on Supabase (Postgres). The connection string lives in
backend/.env as DATABASE_URL, e.g.

    DATABASE_URL=postgresql://postgres.<ref>:<password>@<pooler-host>:6543/postgres

so no credentials are committed. If DATABASE_URL is unset we fall back to a
local SQLite file purely so the app can still boot for offline development.

Each domain package declares its own ORM models against ``Base``; ``Database``
owns the engine, hands out sessions, and creates/upgrades the schema.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import get_settings

Base = declarative_base()


class Database:
    def __init__(self, url: str):
        self.url = url
        self.engine = self._create_engine(url)
        self.session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    @staticmethod
    def _create_engine(url: str) -> Engine:
        if url.startswith("sqlite"):
            return create_engine(url, connect_args={"check_same_thread": False})
        # Supabase/Postgres: pre-ping so dropped pooler connections are recycled
        # transparently instead of erroring on the next request.
        return create_engine(url, pool_pre_ping=True)

    def session(self) -> Session:
        return self.session_factory()

    def create_schema(self) -> None:
        """Create missing tables, then add columns newer than the live schema.

        Tables are created and owned by the Supabase migration (see the Supabase
        project). create_all only fills in anything missing, so it is a no-op
        against the managed schema and still works for the SQLite fallback.
        Callers must import every domain's models module first so ``Base``
        knows about all tables.
        """
        from .schema_upgrades import SchemaUpgrader

        Base.metadata.create_all(bind=self.engine)
        SchemaUpgrader(self.engine).run()


database = Database(get_settings().database_url)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = database.session()
    try:
        yield db
    finally:
        db.close()
