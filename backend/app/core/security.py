"""Password hashing and JWT access tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt


class InvalidToken(Exception):
    pass


class PasswordHasher:
    """Salted PBKDF2-HMAC-SHA256, stored as ``pbkdf2_sha256$<iterations>$<salt>$<hex digest>``.

    Hashes written by earlier versions of the app were bare unsalted SHA-256
    hex digests. Those still verify, and ``needs_rehash`` flags them so the
    login flow can upgrade them transparently.
    """

    SCHEME = "pbkdf2_sha256"
    ITERATIONS = 600_000

    @classmethod
    def hash(cls, password: str) -> str:
        salt = secrets.token_hex(16)
        return f"{cls.SCHEME}${cls.ITERATIONS}${salt}${cls._derive(password, salt, cls.ITERATIONS)}"

    @classmethod
    def verify(cls, password: str, hashed: str) -> bool:
        if not hashed:
            return False
        if not hashed.startswith(f"{cls.SCHEME}$"):
            return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), hashed)
        try:
            _, iterations, salt, digest = hashed.split("$")
            return hmac.compare_digest(cls._derive(password, salt, int(iterations)), digest)
        except ValueError:
            return False

    @classmethod
    def needs_rehash(cls, hashed: str) -> bool:
        return not (hashed or "").startswith(f"{cls.SCHEME}${cls.ITERATIONS}$")

    @staticmethod
    def _derive(password: str, salt: str, iterations: int) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()


class TokenService:
    ALGORITHM = "HS256"

    def __init__(self, secret_key: str, expire_hours: int):
        self.secret_key = secret_key
        self.expire_hours = expire_hours

    def issue(self, user_id: int, role: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(hours=self.expire_hours)
        return jwt.encode({"sub": str(user_id), "role": role, "exp": expire}, self.secret_key, algorithm=self.ALGORITHM)

    def user_id_from(self, token: str) -> int:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.ALGORITHM])
            return int(payload["sub"])
        except (JWTError, KeyError, ValueError) as exc:
            raise InvalidToken from exc
