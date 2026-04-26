"""Tests for the notifier dispatcher."""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet

from tradingagents_web.models import Alert, Analysis
from tradingagents_web.services import notifier, settings_store


@pytest.fixture(autouse=True)
def _enc_key(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())


def _make_analysis(db, *, ticker, decision, confidence, status="completed", error=None):
    row = Analysis(
        run_id=f"r-{ticker}-{decision}-{confidence}-{status}",
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
        error=error,
    )
    if status == "completed":
        row.completed_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.mark.asyncio
async def test_dispatch_first_completion_no_signal_change(app_with_test_db, monkeypatch):
    _, TestSessionLocal = app_with_test_db
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(notifier, "_send_telegram", sender)

    db = TestSessionLocal()
    try:
        a = _make_analysis(db, ticker="AAPL", decision="BUY", confidence=0.7)
        await notifier.dispatch_for_analysis(a.id, session_factory=TestSessionLocal)
        assert db.query(Alert).count() == 0  # defaults skip run_completed
        sender.assert_not_called()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_dispatch_signal_change_creates_alert_and_sends_telegram(
    app_with_test_db, monkeypatch
):
    _, TestSessionLocal = app_with_test_db
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(notifier, "_send_telegram", sender)

    db = TestSessionLocal()
    try:
        settings_store.save_notification_config(
            db, updates={"telegram_bot_token": "T:OK", "telegram_chat_id": "9"}
        )
        _make_analysis(db, ticker="AAPL", decision="HOLD", confidence=0.5)
        curr = _make_analysis(db, ticker="AAPL", decision="BUY", confidence=0.8)
        await notifier.dispatch_for_analysis(curr.id, session_factory=TestSessionLocal)
        types = sorted(r.type for r in db.query(Alert).all())
        assert "signal_change" in types
        assert "confidence_change" in types  # |0.8-0.5|=0.3 > 0.10 default
        sender.assert_awaited()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_dispatch_failed_analysis_creates_run_failed_alert(
    app_with_test_db, monkeypatch
):
    _, TestSessionLocal = app_with_test_db
    monkeypatch.setattr(notifier, "_send_telegram", AsyncMock(return_value=True))

    db = TestSessionLocal()
    try:
        a = _make_analysis(
            db, ticker="AAPL", decision=None, confidence=None,
            status="failed", error="yfinance HTTPError",
        )
        await notifier.dispatch_for_analysis(a.id, session_factory=TestSessionLocal)
        row = db.query(Alert).filter_by(type="run_failed").one()
        assert row.payload["error"] == "yfinance HTTPError"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_telegram_skipped_when_token_missing(app_with_test_db, monkeypatch):
    _, TestSessionLocal = app_with_test_db
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(notifier, "_send_telegram", sender)

    db = TestSessionLocal()
    try:
        _make_analysis(db, ticker="AAPL", decision="HOLD", confidence=0.5)
        curr = _make_analysis(db, ticker="AAPL", decision="BUY", confidence=0.55)
        await notifier.dispatch_for_analysis(curr.id, session_factory=TestSessionLocal)
        sender.assert_not_called()
        # Alert row still created (in-app channel always on)
        assert db.query(Alert).filter_by(type="signal_change").count() == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_dispatch_schedule_failure_creates_alert(app_with_test_db, monkeypatch):
    _, TestSessionLocal = app_with_test_db
    monkeypatch.setattr(notifier, "_send_telegram", AsyncMock(return_value=True))

    db = TestSessionLocal()
    try:
        await notifier.dispatch_schedule_failure(
            schedule_id=42,
            ticker="NVDA",
            error="connection refused",
            session_factory=TestSessionLocal,
        )
        row = db.query(Alert).filter_by(type="schedule_failed").one()
        assert row.schedule_id == 42
        assert row.ticker == "NVDA"
        assert row.payload["error"] == "connection refused"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_dispatch_swallows_exceptions(app_with_test_db, monkeypatch, caplog):
    """Notifier must never raise into the runner."""
    _, TestSessionLocal = app_with_test_db

    def boom(*a, **kw):
        raise RuntimeError("settings broken")
    monkeypatch.setattr(settings_store, "load_notification_config", boom)

    db = TestSessionLocal()
    try:
        a = _make_analysis(db, ticker="AAPL", decision="BUY", confidence=0.7)
    finally:
        db.close()

    # Should not raise
    await notifier.dispatch_for_analysis(a.id, session_factory=TestSessionLocal)
