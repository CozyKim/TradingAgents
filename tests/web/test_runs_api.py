"""API tests for /api/runs."""
import time

import pytest

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Analysis, User
from tradingagents_web.services.event_bus import reset_event_bus

_settings = Settings()


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_event_bus()
    yield
    reset_event_bus()


def _logged_in_client(app_with_test_db, client):
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


def test_create_run_requires_auth(client):
    r = client.post(
        "/api/runs",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "AAPL", "analysis_date": "2026-04-25"},
    )
    assert r.status_code == 401


def test_create_run_returns_run_id_and_persists(monkeypatch, app_with_test_db, client):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    client = _logged_in_client(app_with_test_db, client)
    r = client.post(
        "/api/runs",
        headers={"X-Requested-With": "fetch"},
        json={
            "ticker": "aapl",
            "analysis_date": "2026-04-25",
            "analysts": ["market", "news"],
            "debate_rounds": 1,
        },
    )
    assert r.status_code == 201, r.text
    run_id = r.json()["run_id"]

    _, TestSessionLocal = app_with_test_db
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        db = TestSessionLocal()
        try:
            row = db.query(Analysis).filter_by(run_id=run_id).one()
            if row.status == "completed":
                assert row.ticker == "AAPL"
                assert row.analysts == ["market", "news"]
                assert row.decision == "BUY"
                assert row.final_state is not None
                return
        finally:
            db.close()
        time.sleep(0.05)
    pytest.fail("background task did not complete within 5s")


def test_create_run_validates_payload(app_with_test_db, client):
    client = _logged_in_client(app_with_test_db, client)
    r = client.post(
        "/api/runs",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "", "analysis_date": "2026-04-25"},
    )
    assert r.status_code == 422


def _seed_analyses(TestSessionLocal):
    from datetime import date

    from tradingagents_web.models import Analysis

    db = TestSessionLocal()
    try:
        rows = [
            Analysis(run_id="r-1", ticker="AAPL", analysis_date=date(2026, 4, 20),
                     status="completed", decision="BUY", confidence=0.7,
                     llm_provider="openai", llm_deep_model="x", llm_quick_model="y",
                     debate_rounds=1, analysts=["market"]),
            Analysis(run_id="r-2", ticker="NVDA", analysis_date=date(2026, 4, 21),
                     status="completed", decision="SELL", confidence=0.6,
                     llm_provider="openai", llm_deep_model="x", llm_quick_model="y",
                     debate_rounds=1, analysts=["market"]),
            Analysis(run_id="r-3", ticker="AAPL", analysis_date=date(2026, 4, 22),
                     status="running",
                     llm_provider="openai", llm_deep_model="x", llm_quick_model="y",
                     debate_rounds=1, analysts=["market"]),
        ]
        db.add_all(rows)
        db.commit()
    finally:
        db.close()


def test_list_runs_returns_recent_first(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.get("/api/runs", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert body["items"][0]["run_id"] == "r-3"  # most recent created_at first
    assert body["page"] == 1


def test_list_runs_filter_by_ticker(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.get("/api/runs?ticker=AAPL", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert {item["run_id"] for item in body["items"]} == {"r-1", "r-3"}


def test_list_runs_filter_by_status_and_decision(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.get(
        "/api/runs?status=completed&decision=BUY",
        headers={"X-Requested-With": "fetch"},
    )
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["run_id"] == "r-1"


def test_list_runs_pagination(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.get("/api/runs?page=1&page_size=2", headers={"X-Requested-With": "fetch"})
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3


def test_get_run_detail_returns_full_state(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    _seed_analyses(TestSessionLocal)
    client = _logged_in_client(app_with_test_db, client)
    r = client.get("/api/runs/r-1", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "r-1"
    assert body["decision"] == "BUY"
    assert body["analysts"] == ["market"]


def test_get_run_detail_404(app_with_test_db, client):
    client = _logged_in_client(app_with_test_db, client)
    r = client.get("/api/runs/missing", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 404
