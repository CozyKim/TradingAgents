"""End-to-end happy path for M2: login → create run (fake) → poll until completed → list/detail."""
import time
from datetime import date

import pytest

from tradingagents_web.auth import hash_password
from tradingagents_web.config import Settings
from tradingagents_web.models import User
from tradingagents_web.services.event_bus import reset_event_bus

_settings = Settings()


@pytest.fixture(autouse=True)
def _reset():
    reset_event_bus()
    yield
    reset_event_bus()


def test_full_run_history_flow(monkeypatch, app_with_test_db, client):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        db.add(User(password_hash=hash_password("pw")))
        db.commit()
    finally:
        db.close()

    headers = {"X-Requested-With": "fetch"}

    r = client.post("/api/auth/login", json={"password": "pw"}, headers=headers)
    assert r.status_code == 200

    r = client.post(
        "/api/runs",
        headers=headers,
        json={
            "ticker": "AAPL",
            "analysis_date": str(date(2026, 4, 25)),
            "analysts": ["market", "news"],
            "debate_rounds": 1,
        },
    )
    assert r.status_code == 201
    run_id = r.json()["run_id"]

    # Poll until status moves to completed
    for _ in range(100):
        r = client.get(f"/api/runs/{run_id}", headers=headers)
        if r.json()["status"] == "completed":
            break
        time.sleep(0.05)
    else:
        pytest.fail("Run did not complete in time")

    detail = r.json()
    assert detail["decision"] == "BUY"
    assert detail["final_state"]["market_report"].startswith("Fake market report")

    r = client.get("/api/runs", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(it["run_id"] == run_id for it in items)
