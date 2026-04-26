"""Tests for the Alert ORM model."""
from tradingagents_web.models import Alert


def test_alert_defaults_and_persistence(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        row = Alert(
            type="signal_change",
            ticker="AAPL",
            analysis_id=42,
            payload={"prev": "HOLD", "curr": "BUY", "confidence": 0.78},
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        fetched = db.query(Alert).one()
        assert fetched.read is False
        assert fetched.payload["curr"] == "BUY"
        assert fetched.created_at is not None
        assert fetched.schedule_id is None
    finally:
        db.close()


def test_alert_accepts_schedule_failure_shape(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        row = Alert(
            type="schedule_failed",
            ticker=None,
            schedule_id=7,
            payload={"error": "yfinance HTTPError"},
        )
        db.add(row)
        db.commit()
        assert db.query(Alert).filter_by(type="schedule_failed").count() == 1
    finally:
        db.close()
