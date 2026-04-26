"""Notification settings API tests."""
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import User

_settings = Settings()


@pytest.fixture(autouse=True)
def _enc_key(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())


def _login(app_with_test_db, client):
    """Authenticate client by creating a user and setting a session cookie."""
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        user = User(password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
    finally:
        db.close()
    client.cookies.set(_settings.session_cookie_name, token)
    return client


def test_get_defaults(app_with_test_db, client):
    _login(app_with_test_db, client)
    r = client.get("/api/settings/notifications")
    assert r.status_code == 200
    body = r.json()
    assert body["telegram_bot_token_set"] is False
    assert body["telegram_chat_id"] is None
    assert body["alert_on_signal_change"] is True
    assert body["alert_on_run_completed"] is False
    assert body["confidence_change_threshold"] == 0.10


def test_put_update_partial_and_get(app_with_test_db, client):
    _login(app_with_test_db, client)
    r = client.put(
        "/api/settings/notifications",
        json={"telegram_bot_token": "abc:DEF", "telegram_chat_id": "999"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["telegram_bot_token_set"] is True
    assert body["telegram_chat_id"] == "999"
    assert "telegram_bot_token" not in body or body.get("telegram_bot_token") in (None, "***")


def test_put_validates_threshold(app_with_test_db, client):
    _login(app_with_test_db, client)
    r = client.put(
        "/api/settings/notifications",
        json={"confidence_change_threshold": 5},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 422


def test_test_telegram_with_inline_token(app_with_test_db, client, monkeypatch):
    _login(app_with_test_db, client)
    from tradingagents_web.api import settings_notifications as api

    async def fake_get_me(token):
        assert token == "T:123"
        return {"ok": True, "username": "trbot"}

    monkeypatch.setattr(api.telegram, "get_me", fake_get_me)
    monkeypatch.setattr(api.telegram, "send_message", AsyncMock(return_value=True))

    r = client.post(
        "/api/settings/notifications/test",
        json={"telegram_bot_token": "T:123", "telegram_chat_id": "9"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["bot_username"] == "trbot"
    assert body["error"] is None


def test_test_telegram_with_stored_token(app_with_test_db, client, monkeypatch):
    _login(app_with_test_db, client)
    # Save first
    client.put(
        "/api/settings/notifications",
        json={"telegram_bot_token": "STORED:tok", "telegram_chat_id": "1"},
        headers={"X-Requested-With": "fetch"},
    )

    from tradingagents_web.api import settings_notifications as api

    async def fake_get_me(token):
        assert token == "STORED:tok"
        return {"ok": True, "username": "ok"}

    monkeypatch.setattr(api.telegram, "get_me", fake_get_me)
    monkeypatch.setattr(api.telegram, "send_message", AsyncMock(return_value=True))

    r = client.post(
        "/api/settings/notifications/test",
        json={},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_test_telegram_no_token_returns_422(app_with_test_db, client):
    _login(app_with_test_db, client)
    r = client.post(
        "/api/settings/notifications/test",
        json={},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 422


def test_settings_require_auth(client):
    r = client.get("/api/settings/notifications")
    assert r.status_code == 401
