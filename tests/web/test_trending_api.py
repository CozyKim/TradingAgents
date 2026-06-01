"""Tests for the hot-sector (trending) recommendation API."""

import asyncio

import pytest

from tradingagents_web.schemas.trending import (
    TrendingScanOut,
    TrendingSector,
    TrendingSignals,
)
from tradingagents_web.services.event_bus import AnalysisEvent, get_event_bus, reset_event_bus

XHR_HEADERS = {"X-Requested-With": "fetch"}


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_event_bus()
    yield
    reset_event_bus()


def test_trending_schemas_importable():
    sig = TrendingSignals(web_trend=10, community_volume=20, sentiment=30, momentum=40)
    sector = TrendingSector(name="온디바이스 AI", hotness_score=55.0, signals=sig)
    out = TrendingScanOut(job_id="abc")
    assert sector.signals.momentum == 40
    assert out.job_id == "abc"


def test_start_trending_scan_returns_job_id(auth_client, monkeypatch):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    resp = auth_client.post("/api/sectors/trending", headers=XHR_HEADERS)
    assert resp.status_code == 202, resp.text
    assert resp.json()["job_id"]


def test_trending_stream_emits_done_with_sectors(auth_client, monkeypatch):
    """SSE stream delivers pre-published events — mirrors test_runs_stream.py pattern.

    The TestClient runs a sync event loop. asyncio.create_task() background tasks
    are not awaited between HTTP calls, so we pre-publish history into the bus
    before subscribing (same as test_runs_stream.py which does bus.publish + bus.finish
    before calling client.stream).
    """
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    job_id = auth_client.post(
        "/api/sectors/trending", headers=XHR_HEADERS
    ).json()["job_id"]

    # Pre-populate the bus so the stream subscriber replays from history.
    # This mirrors the test_runs_stream.py pattern exactly.
    bus = get_event_bus()
    bus.publish(job_id, AnalysisEvent(type="progress", data={"stage": "discover"}))
    bus.publish(
        job_id,
        AnalysisEvent(
            type="done",
            data={
                "sectors": [
                    {
                        "name": "온디바이스 AI",
                        "hotness_score": 82.0,
                        "signals": {
                            "web_trend": 80,
                            "community_volume": 75,
                            "sentiment": 85,
                            "momentum": 70,
                        },
                    }
                ]
            },
        ),
    )
    bus.finish(job_id)

    # TestClient consumes SSE as a streaming bytes body (same pattern as test_runs_stream.py).
    with auth_client.stream(
        "GET", f"/api/sectors/trending/{job_id}/stream"
    ) as r:
        assert r.status_code == 200
        body = b"".join(r.iter_bytes()).decode("utf-8")

    assert "event: progress" in body
    assert "event: done" in body
    assert "온디바이스 AI" in body  # matches the done event we published above


def test_execute_trending_scan_publishes_done_with_sectors(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from tradingagents_web.api import sectors as sectors_api
    from tradingagents_web.api.sectors import _execute_trending_scan, get_event_bus
    from tradingagents_web.models import Base
    from tradingagents_web.services.trending_finder import FakeTrendingFinder

    # Provide an in-memory DB so the new persistence path works without prod DB.
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(sectors_api, "_session_factory", TestSession)

    bus = get_event_bus()
    job_id = "drv-test-1"
    finder = FakeTrendingFinder(bus)
    asyncio.run(_execute_trending_scan(finder, job_id))

    events = bus.history(job_id)
    types = [e.type for e in events]
    assert "done" in types
    done = next(e for e in events if e.type == "done")
    names = [s["name"] for s in done.data["sectors"]]
    assert "온디바이스 AI" in names
    assert bus.is_finished(job_id)
