"""End-to-end M3 happy path: holdings/schedules/auto-run wiring."""
import time

import pytest

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Analysis, Schedule, User
from tradingagents_web.services.event_bus import reset_event_bus

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
    return client


def test_m3_happy_path(monkeypatch, app_with_test_db, client):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    client = _login(app_with_test_db, client)
    _, TestSessionLocal = app_with_test_db

    # 1. Add holding
    r = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "AAPL", "qty": 5, "avg_cost": 150},
    )
    assert r.status_code == 201
    hid = r.json()["id"]

    # 2. Toggle monitor → schedule auto-created
    r = client.patch(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
        json={"monitor_enabled": True},
    )
    assert r.status_code == 200

    db = TestSessionLocal()
    try:
        sched = db.query(Schedule).filter_by(holding_id=hid, source="holding").one()
        sid = sched.id
    finally:
        db.close()

    # 3. Trigger run-now via API
    r = client.post(
        f"/api/schedules/{sid}/run",
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]

    # 4. Wait for fake runner to finish
    deadline = time.time() + 5
    r2 = None
    while time.time() < deadline:
        r2 = client.get(f"/api/runs/{run_id}")
        if r2.status_code == 200 and r2.json()["status"] == "completed":
            break
        time.sleep(0.05)
    assert r2 is not None
    assert r2.json()["status"] == "completed"
    assert r2.json()["schedule_id"] == sid

    # 5. Listing schedules + holdings reflects state
    db = TestSessionLocal()
    try:
        analyses = db.query(Analysis).filter_by(schedule_id=sid).all()
        assert len(analyses) == 1
        sched = db.query(Schedule).get(sid)
        assert sched.last_run is not None
    finally:
        db.close()

    # 6. Toggle monitor OFF → schedule removed
    r = client.patch(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
        json={"monitor_enabled": False},
    )
    assert r.status_code == 200
    db = TestSessionLocal()
    try:
        rows = db.query(Schedule).filter_by(holding_id=hid).all()
        assert rows == []
    finally:
        db.close()
