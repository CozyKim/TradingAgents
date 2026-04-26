"""API tests for /api/settings/account."""
from __future__ import annotations

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


def test_backup_requires_auth(client):
    r = client.get("/api/settings/account/backup")
    assert r.status_code == 401


def test_backup_returns_sqlite_attachment(app_with_test_db, client):
    client = _login(app_with_test_db, client)
    r = client.get("/api/settings/account/backup")
    assert r.status_code == 200, r.text
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".db" in cd
    body = r.content
    assert body.startswith(b"SQLite format 3\x00"), "body should be a real SQLite file"
