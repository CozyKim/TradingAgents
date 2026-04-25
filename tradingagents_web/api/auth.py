"""Login / logout / current-user API."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, SecretStr
from sqlalchemy.orm import Session

from tradingagents_web.auth import (
    create_session,
    delete_session,
    get_current_user,
    require_xhr,
    verify_password,
)
from tradingagents_web.config import Settings
from tradingagents_web.db import get_db
from tradingagents_web.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])
_settings = Settings()


class LoginRequest(BaseModel):
    password: SecretStr


class LoginResponse(BaseModel):
    ok: bool


class MeResponse(BaseModel):
    id: int


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> LoginResponse:
    user = db.query(User).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No user account configured. Run `tradingagents-web set-password`.",
        )
    if not verify_password(body.password.get_secret_value(), user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    token = create_session(db, user.id)
    response.set_cookie(
        key=_settings.session_cookie_name,
        value=token,
        max_age=_settings.session_max_age_seconds,
        httponly=True,
        secure=_settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return LoginResponse(ok=True)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> dict[str, bool]:
    token = request.cookies.get(_settings.session_cookie_name)
    if token:
        delete_session(db, token)
    response.delete_cookie(
        key=_settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=_settings.cookie_secure,
        samesite="strict",
    )
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(id=user.id)
