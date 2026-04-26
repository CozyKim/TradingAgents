"""API tests for /api/settings/account."""
from __future__ import annotations

from tradingagents_web.auth import create_session, hash_password
from tradingagents_web.config import Settings
from tradingagents_web.models import User

_settings = Settings()


def _login(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        user = User(password_hash=hash_password("testpass"))
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
        user_id = user.id
    finally:
        db.close()
    client.cookies.set(_settings.session_cookie_name, token)
    return client, user_id


def _make_extra_session(app_with_test_db, user_id):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        return create_session(db, user_id)
    finally:
        db.close()


def test_backup_requires_auth(client):
    r = client.get("/api/settings/account/backup")
    assert r.status_code == 401


def test_backup_returns_sqlite_attachment(app_with_test_db, client):
    client, _ = _login(app_with_test_db, client)
    r = client.get("/api/settings/account/backup")
    assert r.status_code == 200, r.text
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd
    assert ".db" in cd
    body = r.content
    assert body.startswith(b"SQLite format 3\x00"), "body should be a real SQLite file"


def test_password_change_requires_correct_current(app_with_test_db, client):
    client, _ = _login(app_with_test_db, client)
    r = client.put(
        "/api/settings/account/password",
        json={"current_password": "wrong", "new_password": "newpass1234"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 401


def test_password_change_updates_hash_and_revokes_other_sessions(app_with_test_db, client):
    client, user_id = _login(app_with_test_db, client)
    other_token = _make_extra_session(app_with_test_db, user_id)

    r = client.put(
        "/api/settings/account/password",
        json={
            "current_password": "testpass",
            "new_password": "newpass1234",
            "revoke_other_sessions": True,
        },
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200, r.text

    # The other session should no longer authenticate. Swap the client's
    # session cookie to the other token so there's no ambiguity in the
    # request's Cookie header (TestClient merges per-request cookies with
    # the client jar, which can cause duplicate Cookie entries).
    client.cookies.clear()
    client.cookies.set(_settings.session_cookie_name, other_token)
    r2 = client.get("/api/auth/me")
    assert r2.status_code == 401

    # Logging in with the new password works (proves the hash was updated).
    client.cookies.clear()
    r3 = client.post(
        "/api/auth/login",
        json={"password": "newpass1234"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r3.status_code == 200


def test_password_change_keeps_other_sessions_when_revoke_false(app_with_test_db, client):
    client, user_id = _login(app_with_test_db, client)
    other_token = _make_extra_session(app_with_test_db, user_id)

    r = client.put(
        "/api/settings/account/password",
        json={
            "current_password": "testpass",
            "new_password": "newpass1234",
            "revoke_other_sessions": False,
        },
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200

    # Other session still works.
    client.cookies.clear()
    client.cookies.set(_settings.session_cookie_name, other_token)
    r2 = client.get("/api/auth/me")
    assert r2.status_code == 200


def test_password_change_rejects_short_password(app_with_test_db, client):
    client, _ = _login(app_with_test_db, client)
    r = client.put(
        "/api/settings/account/password",
        json={"current_password": "testpass", "new_password": "short"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 422


def test_password_change_requires_csrf_header(app_with_test_db, client):
    client, _ = _login(app_with_test_db, client)
    r = client.put(
        "/api/settings/account/password",
        json={"current_password": "testpass", "new_password": "newpass1234"},
    )
    assert r.status_code == 403
