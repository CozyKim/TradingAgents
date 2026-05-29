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


import asyncio

XHR_HEADERS = {"X-Requested-With": "fetch"}


def test_execute_trending_scan_saves_row_and_scan_id(db_session, monkeypatch):
    from tradingagents_web.api import sectors as sectors_api
    from tradingagents_web.services.event_bus import reset_event_bus
    from tradingagents_web.services.trending_finder import FakeTrendingFinder
    from tradingagents_web.models import TrendingScan

    reset_event_bus()
    monkeypatch.setattr(sectors_api, "_session_factory", lambda: db_session)

    bus = sectors_api.get_event_bus()
    finder = FakeTrendingFinder(bus)
    asyncio.run(sectors_api._execute_trending_scan(finder, "job-save-1"))

    rows = db_session.query(TrendingScan).all()
    assert len(rows) == 1
    assert len(rows[0].sectors) == 3  # FakeTrendingFinder returns 3 dummies

    done = next(e for e in bus.history("job-save-1") if e.type == "done")
    assert done.data["scan_id"] == rows[0].id


def test_list_and_get_trending_scans(auth_client, db_session):
    from tradingagents_web.models import TrendingScan

    db_session.add(TrendingScan(sectors=[{"name": "A", "hotness_score": 50}]))
    db_session.add(TrendingScan(sectors=[{"name": "B", "hotness_score": 60}, {"name": "C", "hotness_score": 40}]))
    db_session.commit()

    listing = auth_client.get("/api/sectors/trending/scans")
    assert listing.status_code == 200
    body = listing.json()
    assert len(body) == 2
    assert {item["sector_count"] for item in body} == {1, 2}

    scan_id = body[0]["id"]
    detail = auth_client.get(f"/api/sectors/trending/scans/{scan_id}")
    assert detail.status_code == 200
    assert "sectors" in detail.json()

    missing = auth_client.get("/api/sectors/trending/scans/999999")
    assert missing.status_code == 404
