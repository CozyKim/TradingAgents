"""Tests for TrendingScan persistence + trending scan history API."""

from tradingagents_web.models import TrendingScan


def test_trending_scan_persists(db_session):
    row = TrendingScan(sectors=[{"name": "온디바이스 AI", "hotness_score": 80}])
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    assert row.id is not None
    assert row.created_at is not None
    assert row.sectors == [{"name": "온디바이스 AI", "hotness_score": 80}]
