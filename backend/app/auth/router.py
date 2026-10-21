"""Auth endpoints — login and current-user lookup."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from .dependencies import get_current_user
from .models import User
from .schemas import LocationUpdate, LoginRequest, TokenResponse, UserOut
from .service import AuthService, InvalidCredentials

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    try:
        user, token = AuthService(db).login(body.email, body.password)
    except InvalidCredentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(access_token=token, role=user.role, name=user.name)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.put("/me/location", response_model=UserOut)
def update_location(
    body: LocationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return UserOut.model_validate(AuthService(db).update_location(current_user, body.lat, body.lng))
