"""SSE stream endpoint test using TestClient.stream()."""
from datetime import date

import pytest

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Analysis, User
from tradingagents_web.services.event_bus import (
    AnalysisEvent,
    get_event_bus,
    reset_event_bus,
)

_settings = Settings()


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_event_bus()
    yield
    reset_event_bus()


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


def test_stream_replays_history_then_closes_when_finished(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        db.add(Analysis(
            run_id="r-stream", ticker="AAPL", analysis_date=date(2026, 4, 25),
            status="completed", decision="BUY", confidence=0.7,
            llm_provider="o", llm_deep_model="d", llm_quick_model="q",
            debate_rounds=1, analysts=["market"],
        ))
        db.commit()
    finally:
        db.close()

    bus = get_event_bus()
    bus.publish("r-stream", AnalysisEvent(type="agent_message", data={"text": "hi"}))
    bus.publish("r-stream", AnalysisEvent(type="done", data={"decision": "BUY"}))
    bus.finish("r-stream")

    _login(app_with_test_db, client)

    with client.stream(
        "GET",
        "/api/runs/r-stream/stream",
        headers={"X-Requested-With": "fetch"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = b"".join(response.iter_bytes()).decode("utf-8")

    assert "event: agent_message" in body
    assert "event: done" in body
    assert "event: close" in body


def test_stream_404_when_run_missing(app_with_test_db, client):
    _login(app_with_test_db, client)
    with client.stream("GET", "/api/runs/none/stream", headers={"X-Requested-With": "fetch"}) as r:
        assert r.status_code == 404


def test_stream_requires_auth(client):
    with client.stream("GET", "/api/runs/x/stream", headers={"X-Requested-With": "fetch"}) as r:
        assert r.status_code == 401
