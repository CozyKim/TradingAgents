"""API tests for /api/runs."""
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
    body = r.json()
    assert "run_id" in body and len(body["run_id"]) > 0

    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        row = db.query(Analysis).filter_by(run_id=body["run_id"]).one()
        assert row.ticker == "AAPL"
        assert row.status in {"running", "completed"}
        assert row.analysts == ["market", "news"]
    finally:
        db.close()


def test_create_run_validates_payload(app_with_test_db, client):
    client = _logged_in_client(app_with_test_db, client)
    r = client.post(
        "/api/runs",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "", "analysis_date": "2026-04-25"},
    )
    assert r.status_code == 422
