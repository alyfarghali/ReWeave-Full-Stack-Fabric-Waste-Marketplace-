from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.security import PasswordHasher, TokenService
from .models import User


class InvalidCredentials(Exception):
    pass


def token_service() -> TokenService:
    settings = get_settings()
    return TokenService(settings.secret_key, settings.token_expire_hours)


class AuthService:
    def __init__(self, db: Session, tokens: TokenService | None = None):
        self.db = db
        self.tokens = tokens or token_service()

    def login(self, email: str, password: str) -> tuple[User, str]:
        """Return the user and a fresh access token, or raise InvalidCredentials."""
        user = self.db.query(User).filter(User.email == email).first()
        if not user or not PasswordHasher.verify(password, user.password_hash):
            raise InvalidCredentials
        if PasswordHasher.needs_rehash(user.password_hash):
            user.password_hash = PasswordHasher.hash(password)
            self.db.commit()
        return user, self.tokens.issue(user.id, user.role)

    def user_for_token(self, token: str) -> User | None:
        return self.db.get(User, self.tokens.user_id_from(token))

    def update_location(self, user: User, lat: float, lng: float) -> User:
        user.lat = lat
        user.lng = lng
        self.db.commit()
        self.db.refresh(user)
        return user
