"""API tests for /api/schedules."""
from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import User

_settings = Settings()


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
    return client


def test_list_schedules_empty(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.get("/api/schedules")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_create_schedule(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/schedules",
        headers={"X-Requested-With": "fetch"},
        json={
            "name": "AAPL daily",
            "ticker": "aapl",
            "cron_expr": "30 16 * * 1-5",
            "preset": {"analysts": ["market"], "debate_rounds": 1},
        },
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["ticker"] == "AAPL"
    assert item["source"] == "user"


def test_create_schedule_invalid_cron(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/schedules",
        headers={"X-Requested-With": "fetch"},
        json={
            "name": "bad",
            "ticker": "AAPL",
            "cron_expr": "not a cron",
            "preset": {"analysts": ["market"], "debate_rounds": 1},
        },
    )
    assert r.status_code == 422


def test_pause_resume_schedule(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/schedules",
        headers={"X-Requested-With": "fetch"},
        json={
            "name": "S",
            "ticker": "AAPL",
            "cron_expr": "0 9 * * *",
            "preset": {"analysts": ["market"], "debate_rounds": 1},
        },
    )
    sid = r.json()["id"]

    r2 = client.patch(
        f"/api/schedules/{sid}",
        headers={"X-Requested-With": "fetch"},
        json={"active": False},
    )
    assert r2.status_code == 200
    assert r2.json()["active"] is False

    r3 = client.patch(
        f"/api/schedules/{sid}",
        headers={"X-Requested-With": "fetch"},
        json={"active": True},
    )
    assert r3.status_code == 200
    assert r3.json()["active"] is True


def test_delete_schedule(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/schedules",
        headers={"X-Requested-With": "fetch"},
        json={
            "name": "Z",
            "ticker": "AAPL",
            "cron_expr": "0 9 * * *",
            "preset": {"analysts": ["market"], "debate_rounds": 1},
        },
    )
    sid = r.json()["id"]
    r2 = client.delete(
        f"/api/schedules/{sid}",
        headers={"X-Requested-With": "fetch"},
    )
    assert r2.status_code == 204


def test_run_now_creates_analysis(monkeypatch, app_with_test_db, client):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/schedules",
        headers={"X-Requested-With": "fetch"},
        json={
            "name": "X",
            "ticker": "AAPL",
            "cron_expr": "0 9 * * *",
            "preset": {"analysts": ["market"], "debate_rounds": 1},
        },
    )
    sid = r.json()["id"]
    r2 = client.post(
        f"/api/schedules/{sid}/run",
        headers={"X-Requested-With": "fetch"},
    )
    assert r2.status_code == 202, r2.text
    body = r2.json()
    assert "run_id" in body
