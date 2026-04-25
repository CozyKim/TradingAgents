"""Authentication utilities: password hashing, session tokens, FastAPI deps."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.config import Settings
from tradingagents_web.db import get_db
from tradingagents_web.models import Session as SessionModel, User
from tradingagents_web.models.base import utcnow

_settings = Settings()


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (cost=12 default)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time verify against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_session_token() -> str:
    """Generate a cryptographically secure random session ID (URL-safe)."""
    return secrets.token_urlsafe(32)


def session_expiry() -> "datetime":
    """Return the expiry datetime for a freshly issued session."""
    return utcnow() + timedelta(seconds=_settings.session_max_age_seconds)


def create_session(db: OrmSession, user_id: int) -> str:
    """Persist a new session row and return its token."""
    token = generate_session_token()
    sess = SessionModel(id=token, user_id=user_id, expires_at=session_expiry())
    db.add(sess)
    db.commit()
    return token


def get_session_by_token(db: OrmSession, token: str) -> SessionModel | None:
    """Look up an active (non-expired) session row."""
    sess = db.query(SessionModel).filter_by(id=token).first()
    if sess is None:
        return None
    expires_at = sess.expires_at
    # SQLite returns naive datetimes; normalise to UTC-aware for comparison.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= utcnow():
        return None
    return sess


def sliding_extend(db: OrmSession, sess: SessionModel) -> None:
    """Extend session expiry on use (sliding window)."""
    sess.expires_at = session_expiry()
    db.commit()


def delete_session(db: OrmSession, token: str) -> None:
    """Remove a session row (logout)."""
    db.query(SessionModel).filter_by(id=token).delete()
    db.commit()


def get_current_user(
    request: Request,
    db: Annotated[OrmSession, Depends(get_db)],
) -> User:
    """FastAPI dependency: return current user or raise 401."""
    token = request.cookies.get(_settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    sess = get_session_by_token(db, token)
    if sess is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid or expired")
    user = db.query(User).filter_by(id=sess.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User missing")
    sliding_extend(db, sess)
    return user
