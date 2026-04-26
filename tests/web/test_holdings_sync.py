"""Tests for holdings_sync.sync_holding_monitor."""
from tradingagents_web.models import Holding, Schedule
from tradingagents_web.services.holdings_sync import (
    DEFAULT_MONITOR_CRON,
    sync_holding_monitor,
)


def test_enable_creates_schedule(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        h = Holding(ticker="AAPL", qty=1, avg_cost=10, monitor_enabled=True)
        db.add(h)
        db.commit()
        db.refresh(h)
        sync_holding_monitor(db, h)
        db.commit()
        rows = db.query(Schedule).filter_by(holding_id=h.id, source="holding").all()
        assert len(rows) == 1
        assert rows[0].cron_expr == DEFAULT_MONITOR_CRON
        assert rows[0].active is True
    finally:
        db.close()


def test_disable_removes_schedule(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        h = Holding(ticker="NVDA", qty=1, avg_cost=10, monitor_enabled=True)
        db.add(h)
        db.commit()
        db.refresh(h)
        sync_holding_monitor(db, h)
        db.commit()
        h.monitor_enabled = False
        sync_holding_monitor(db, h)
        db.commit()
        rows = db.query(Schedule).filter_by(holding_id=h.id, source="holding").all()
        assert rows == []
    finally:
        db.close()


def test_enable_idempotent(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        h = Holding(ticker="MSFT", qty=1, avg_cost=10, monitor_enabled=True)
        db.add(h)
        db.commit()
        db.refresh(h)
        sync_holding_monitor(db, h)
        sync_holding_monitor(db, h)
        db.commit()
        rows = db.query(Schedule).filter_by(holding_id=h.id, source="holding").all()
        assert len(rows) == 1
    finally:
        db.close()
