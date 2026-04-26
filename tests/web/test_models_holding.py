"""Tests for Holding ORM model."""
from tradingagents_web.models import Holding


def test_holding_minimal_fields(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        h = Holding(ticker="AAPL", qty=10.0, avg_cost=150.0)
        db.add(h)
        db.commit()
        db.refresh(h)
        assert h.id > 0
        assert h.monitor_enabled is False
        assert h.notes is None
        assert h.created_at is not None
        assert h.updated_at is not None
    finally:
        db.close()


def test_holding_unique_ticker(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        db.add(Holding(ticker="NVDA", qty=1, avg_cost=900.0))
        db.commit()
        db.add(Holding(ticker="NVDA", qty=2, avg_cost=950.0))
        import sqlalchemy.exc
        try:
            db.commit()
            raise AssertionError("expected unique violation")
        except sqlalchemy.exc.IntegrityError:
            db.rollback()
    finally:
        db.close()
