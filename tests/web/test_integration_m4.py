"""End-to-end M4 happy path: signal change → Alert row + Telegram dispatch
visible through the alerts API."""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Analysis, User
from tradingagents_web.services import notifier

_settings = Settings()


@pytest.fixture(autouse=True)
def _enc_key(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())


def _login(app_with_test_db, client):
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


def _seed_analysis(db, *, ticker, decision, confidence, status="completed"):
    row = Analysis(
        run_id=f"r-{ticker}-{decision}-{confidence}",
        ticker=ticker,
        analysis_date=date(2026, 4, 26),
        status=status,
        decision=decision,
        confidence=confidence,
        llm_provider="x",
        llm_deep_model="x",
        llm_quick_model="x",
        debate_rounds=1,
        analysts=["market"],
    )
    if status == "completed":
        row.completed_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.mark.asyncio
async def test_m4_happy_path_signal_change_visible_via_api(
    monkeypatch, app_with_test_db, client
):
    """Seed prior + current analyses with different decisions, dispatch the
    notifier, and verify the alert is exposed through the alerts API and
    that Telegram fanout was invoked."""
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(notifier, "_send_telegram", sender)

    client = _login(app_with_test_db, client)
    _, TestSessionLocal = app_with_test_db

    # 1. Save Telegram config via API
    r = client.put(
        "/api/settings/notifications",
        headers={"X-Requested-With": "fetch"},
        json={"telegram_bot_token": "T:OK", "telegram_chat_id": "9"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["telegram_bot_token_set"] is True

    # 2. Seed two analyses (HOLD then BUY) — drives signal_change + confidence_change
    db = TestSessionLocal()
    try:
        _seed_analysis(db, ticker="AAPL", decision="HOLD", confidence=0.5)
        curr = _seed_analysis(db, ticker="AAPL", decision="BUY", confidence=0.85)
        curr_id = curr.id
    finally:
        db.close()

    # 3. Dispatch the notifier (this is what _execute_and_persist does after a run)
    await notifier.dispatch_for_analysis(curr_id, session_factory=TestSessionLocal)

    # 4. Telegram mock was called (signal + confidence both fire → at least 1 push)
    sender.assert_awaited()

    # 5. Alert row visible via /api/alerts
    r = client.get("/api/alerts?type=signal_change")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["ticker"] == "AAPL"
    assert item["payload"]["prev"] == "HOLD"
    assert item["payload"]["curr"] == "BUY"
    assert item["read"] is False

    # 6. Unread count reflects the unread signal_change (and any confidence_change)
    r = client.get("/api/alerts/unread-count")
    assert r.status_code == 200
    assert r.json()["unread"] >= 1

    # 7. Mark single alert as read
    r = client.post(
        f"/api/alerts/{item['id']}/read",
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200

    # 8. After mark-read, listing read=true returns this row
    r = client.get("/api/alerts?type=signal_change&read=true")
    assert r.json()["total"] == 1


@pytest.mark.asyncio
async def test_m4_failure_path_run_failed_alert_visible(
    monkeypatch, app_with_test_db, client
):
    """A failed analysis triggers a run_failed alert visible via the API."""
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(notifier, "_send_telegram", sender)

    client = _login(app_with_test_db, client)
    _, TestSessionLocal = app_with_test_db

    db = TestSessionLocal()
    try:
        a = _seed_analysis(
            db, ticker="MSFT", decision=None, confidence=None, status="failed"
        )
        a.error = "yfinance HTTPError"
        db.commit()
        aid = a.id
    finally:
        db.close()

    await notifier.dispatch_for_analysis(aid, session_factory=TestSessionLocal)

    r = client.get("/api/alerts?type=run_failed")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["payload"]["error"] == "yfinance HTTPError"
