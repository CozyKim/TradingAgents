"""Pydantic schemas for the notification settings API."""
from pydantic import BaseModel, Field


class NotificationSettingsResponse(BaseModel):
    """Response shape — never includes the raw bot token."""

    telegram_bot_token_set: bool
    telegram_chat_id: str | None
    alert_on_signal_change: bool
    alert_on_run_completed: bool
    alert_on_run_failed: bool
    alert_on_schedule_failed: bool
    confidence_change_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class NotificationSettingsUpdate(BaseModel):
    """Partial update — every field optional. Token only included when (re)setting."""

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    alert_on_signal_change: bool | None = None
    alert_on_run_completed: bool | None = None
    alert_on_run_failed: bool | None = None
    alert_on_schedule_failed: bool | None = None
    confidence_change_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class TelegramTestRequest(BaseModel):
    """Optional one-shot token for testing without persisting."""

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


class TelegramTestResponse(BaseModel):
    ok: bool
    bot_username: str | None = None
    error: str | None = None
