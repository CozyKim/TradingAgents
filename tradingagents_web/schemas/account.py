"""Pydantic schemas for /api/settings/account."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, SecretStr


class PasswordChangeRequest(BaseModel):
    current_password: SecretStr
    new_password: SecretStr = Field(min_length=8)
    revoke_other_sessions: bool = True


class PasswordChangeResponse(BaseModel):
    ok: bool


class SessionItem(BaseModel):
    id_masked: str
    expires_at: datetime
    is_current: bool


class SessionListResponse(BaseModel):
    sessions: list[SessionItem]


class RestoreResponse(BaseModel):
    ok: bool
    detail: str | None = None
