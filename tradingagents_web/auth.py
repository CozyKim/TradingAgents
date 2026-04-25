"""Authentication utilities: password hashing, session tokens, FastAPI deps."""
import secrets
from datetime import timedelta

import bcrypt

from tradingagents_web.config import Settings
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
