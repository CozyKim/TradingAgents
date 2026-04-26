"""API tests for /api/holdings."""
from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Schedule, User

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


def test_list_holdings_requires_auth(client):
    r = client.get("/api/holdings")
    assert r.status_code == 401


def test_create_then_list_holding(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "aapl", "qty": 10, "avg_cost": 150.0},
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["ticker"] == "AAPL"
    assert item["monitor_enabled"] is False

    r = client.get("/api/holdings")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


def test_update_holding_qty(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "AAPL", "qty": 1, "avg_cost": 100},
    )
    hid = r.json()["id"]
    r2 = client.patch(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
        json={"qty": 5},
    )
    assert r2.status_code == 200
    assert r2.json()["qty"] == 5


def test_toggle_monitor_creates_schedule(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "MSFT", "qty": 1, "avg_cost": 100},
    )
    hid = r.json()["id"]
    r2 = client.patch(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
        json={"monitor_enabled": True},
    )
    assert r2.status_code == 200
    assert r2.json()["monitor_enabled"] is True

    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        rows = db.query(Schedule).filter_by(holding_id=hid, source="holding").all()
        assert len(rows) == 1
        assert rows[0].active is True
    finally:
        db.close()

    r3 = client.patch(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
        json={"monitor_enabled": False},
    )
    assert r3.status_code == 200
    db = TestSessionLocal()
    try:
        rows = db.query(Schedule).filter_by(holding_id=hid, source="holding").all()
        assert rows == []
    finally:
        db.close()


def test_delete_holding(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json={"ticker": "TSLA", "qty": 1, "avg_cost": 200},
    )
    hid = r.json()["id"]
    r2 = client.delete(
        f"/api/holdings/{hid}",
        headers={"X-Requested-With": "fetch"},
    )
    assert r2.status_code == 204
    r3 = client.get("/api/holdings")
    assert r3.json()["items"] == []


def test_create_duplicate_ticker_returns_409(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    payload = {"ticker": "AAPL", "qty": 1, "avg_cost": 100}
    r1 = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json=payload,
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/holdings",
        headers={"X-Requested-With": "fetch"},
        json=payload,
    )
    assert r2.status_code == 409
