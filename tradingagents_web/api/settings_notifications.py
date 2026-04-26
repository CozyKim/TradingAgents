"""Notification settings API: GET/PUT current config + POST test."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as OrmSession

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import User
from tradingagents_web.schemas.notification import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    TelegramTestRequest,
    TelegramTestResponse,
)
from tradingagents_web.services import settings_store, telegram

router = APIRouter(prefix="/api/settings/notifications", tags=["settings"])


def _to_response(cfg: dict) -> NotificationSettingsResponse:
    return NotificationSettingsResponse(
        telegram_bot_token_set=cfg["telegram_bot_token_set"],
        telegram_chat_id=cfg["telegram_chat_id"],
        alert_on_signal_change=cfg["alert_on_signal_change"],
        alert_on_run_completed=cfg["alert_on_run_completed"],
        alert_on_run_failed=cfg["alert_on_run_failed"],
        alert_on_schedule_failed=cfg["alert_on_schedule_failed"],
        confidence_change_threshold=cfg["confidence_change_threshold"],
        web_base_url=cfg.get("web_base_url"),
    )


@router.get("", response_model=NotificationSettingsResponse)
def get_notifications(
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> NotificationSettingsResponse:
    """Return the current notification settings (token never included)."""
    cfg = settings_store.load_notification_config(db)
    return _to_response(cfg)


@router.put("", response_model=NotificationSettingsResponse)
def update_notifications(
    payload: NotificationSettingsUpdate,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> NotificationSettingsResponse:
    """Partial update; absent fields preserve their stored values."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    settings_store.save_notification_config(db, updates=updates)
    return _to_response(settings_store.load_notification_config(db))


@router.post("/test", response_model=TelegramTestResponse)
async def test_telegram(
    payload: TelegramTestRequest,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> TelegramTestResponse:
    """Validate a Telegram token (and optionally a chat_id) end-to-end."""
    cfg = settings_store.load_notification_config(db)
    token = payload.telegram_bot_token or cfg.get("telegram_bot_token")
    chat_id = payload.telegram_chat_id or cfg.get("telegram_chat_id")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No Telegram bot token configured",
        )
    info = await telegram.get_me(token)
    if not info.get("ok"):
        return TelegramTestResponse(ok=False, error=info.get("error", "unknown"))
    if chat_id:
        sent = await telegram.send_message(
            bot_token=token,
            chat_id=chat_id,
            text="✅ TradingAgents test message",
        )
        if not sent:
            return TelegramTestResponse(
                ok=False,
                bot_username=info.get("username"),
                error="sendMessage failed",
            )
    return TelegramTestResponse(ok=True, bot_username=info.get("username"))
