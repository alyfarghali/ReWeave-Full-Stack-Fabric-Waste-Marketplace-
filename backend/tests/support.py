"""Shared test harness: an isolated in-memory database and an API client with per-role tokens."""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.auth.models import Role, User  # noqa: E402
from app.auth.service import token_service  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import PasswordHasher  # noqa: E402

# Importing these registers every table on Base.metadata.
import app.destinations.models  # noqa: E402,F401
import app.marketplace.models  # noqa: E402,F401

USERS = {
    Role.FACTORY: ("factory@test.local", "Factory Worker"),
    Role.ADMIN: ("admin@test.local", "Admin"),
    Role.BUYER: ("buyer@test.local", "Looptex Recyclers"),
}
PASSWORD = "secret-password"


class ApiHarness:
    def __init__(self, *routers):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        app = FastAPI()
        for router in routers:
            app.include_router(router)
        app.dependency_overrides[get_db] = self._db
        self.client = TestClient(app)

        self.tokens = {}
        with self.Session() as db:
            for role, (email, name) in USERS.items():
                user = User(email=email, name=name, role=role, password_hash=PasswordHasher.hash(PASSWORD))
                db.add(user)
                db.flush()
                self.tokens[role] = token_service().issue(user.id, role)
            db.commit()

    def _db(self):
        db = self.Session()
        try:
            yield db
        finally:
            db.close()

    def auth(self, role: str) -> dict:
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    def close(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()
