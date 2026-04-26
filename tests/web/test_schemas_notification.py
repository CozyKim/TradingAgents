"""Tests for notification pydantic schemas."""
import pytest
from pydantic import ValidationError

from tradingagents_web.schemas.notification import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    TelegramTestRequest,
)


def test_notification_update_threshold_bounds():
    with pytest.raises(ValidationError):
        NotificationSettingsUpdate(confidence_change_threshold=-0.1)
    with pytest.raises(ValidationError):
        NotificationSettingsUpdate(confidence_change_threshold=1.1)


def test_notification_update_partial_ok():
    upd = NotificationSettingsUpdate(alert_on_signal_change=False)
    assert upd.alert_on_signal_change is False
    assert upd.telegram_chat_id is None


def test_response_masks_token_presence():
    resp = NotificationSettingsResponse(
        telegram_bot_token_set=True,
        telegram_chat_id="123",
        alert_on_signal_change=True,
        alert_on_run_completed=False,
        alert_on_run_failed=True,
        alert_on_schedule_failed=True,
        confidence_change_threshold=0.10,
    )
    assert resp.telegram_bot_token_set is True


def test_telegram_test_request_accepts_empty_or_token():
    TelegramTestRequest()
    TelegramTestRequest(telegram_bot_token="abc:def")
