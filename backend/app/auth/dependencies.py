"""FastAPI dependencies other domains use to require a logged-in user."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import InvalidToken
from .models import Role, User
from .service import AuthService

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        user = AuthService(db).user_for_token(credentials.credentials)
    except InvalidToken:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(*roles: str):
    """Dependency factory: 403 unless the current user has one of ``roles``."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if not user.has_role(*roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
        return user

    return dependency


# Shared guards. Operators run the factory floor (scanning, listing lots);
# admins additionally manage inventory and see the operations dashboard.
require_operator = require_role(Role.FACTORY, Role.ADMIN)
require_admin = require_role(Role.ADMIN)
require_purchaser = require_role(Role.BUYER, Role.ADMIN)
