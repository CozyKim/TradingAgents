"""Tests for the hot-sector (trending) recommendation API."""

from tradingagents_web.schemas.trending import (
    TrendingScanOut,
    TrendingSector,
    TrendingSignals,
)


def test_trending_schemas_importable():
    sig = TrendingSignals(web_trend=10, community_volume=20, sentiment=30, momentum=40)
    sector = TrendingSector(name="온디바이스 AI", hotness_score=55.0, signals=sig)
    out = TrendingScanOut(job_id="abc")
    assert sector.signals.momentum == 40
    assert out.job_id == "abc"


import os

from tradingagents_web.services.event_bus import AnalysisEvent, get_event_bus

XHR_HEADERS = {"X-Requested-With": "fetch"}


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
    assert "온디바이스 AI" in body  # FakeTrendingFinder dummy
