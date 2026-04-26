"""Alerts API endpoint tests."""
from datetime import datetime, timezone

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import Alert, User

_settings = Settings()


def _login(app_with_test_db, client):
    """Authenticate client by creating a user and setting a session cookie."""
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


def _seed(db, *rows):
    """Add rows to DB and commit."""
    for r in rows:
        db.add(r)
    db.commit()


def _alert(**kw):
    """Build an Alert instance with sensible defaults."""
    base = dict(
        type="signal_change",
        ticker="AAPL",
        analysis_id=None,
        schedule_id=None,
        payload={},
        read=False,
        created_at=datetime.now(timezone.utc),
    )
    base.update(kw)
    return Alert(**base)


def test_list_alerts_pagination(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        _seed(db, *[_alert(ticker=f"T{i}") for i in range(25)])
    finally:
        db.close()

    r = client.get("/api/alerts?page=1&page_size=10")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 25
    assert len(body["items"]) == 10
    assert body["page"] == 1


def test_list_alerts_filter_by_read(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        _seed(db, _alert(read=True), _alert(read=False), _alert(read=False))
    finally:
        db.close()

    r = client.get("/api/alerts?read=false")
    assert r.json()["total"] == 2


def test_list_alerts_filter_by_type(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        _seed(db, _alert(type="signal_change"), _alert(type="run_failed"))
    finally:
        db.close()

    r = client.get("/api/alerts?type=run_failed")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["type"] == "run_failed"


def test_unread_count(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        _seed(db, _alert(read=True), _alert(read=False), _alert(read=False))
    finally:
        db.close()

    r = client.get("/api/alerts/unread-count")
    assert r.status_code == 200
    assert r.json() == {"unread": 2}


def test_mark_read(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        a = _alert()
        db.add(a)
        db.commit()
        db.refresh(a)
        aid = a.id
    finally:
        db.close()

    r = client.post(
        f"/api/alerts/{aid}/read",
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200

    # Reload from a fresh session to bypass identity-map cache
    db2 = TestSessionLocal()
    try:
        refreshed = db2.get(Alert, aid)
        assert refreshed.read is True
    finally:
        db2.close()


def test_mark_read_404(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.post(
        "/api/alerts/999999/read",
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 404


def test_mark_all_read(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        _seed(db, _alert(read=False), _alert(read=False), _alert(read=True))
    finally:
        db.close()

    r = client.post(
        "/api/alerts/read-all",
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200
    assert r.json() == {"marked": 2}

    db2 = TestSessionLocal()
    try:
        assert db2.query(Alert).filter_by(read=False).count() == 0
    finally:
        db2.close()


def test_alerts_require_auth(client):
    r = client.get("/api/alerts")
    assert r.status_code == 401
