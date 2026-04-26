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


def test_sessions_list_marks_current(app_with_test_db, client):
    client, user_id = _login(app_with_test_db, client)
    _make_extra_session(app_with_test_db, user_id)
    _make_extra_session(app_with_test_db, user_id)

    r = client.get("/api/settings/account/sessions")
    assert r.status_code == 200
    body = r.json()
    items = body["sessions"]
    assert len(items) == 3
    current = [s for s in items if s["is_current"]]
    assert len(current) == 1, "exactly one session should be marked current"
    for s in items:
        assert "id_masked" in s
        # masked token is short and contains an ellipsis (or is "***" for short ids)
        assert len(s["id_masked"]) <= 12


def test_sessions_list_requires_auth(client):
    r = client.get("/api/settings/account/sessions")
    assert r.status_code == 401


def test_sessions_revoke_others_keeps_current(app_with_test_db, client):
    client, user_id = _login(app_with_test_db, client)
    other = _make_extra_session(app_with_test_db, user_id)

    r = client.post(
        "/api/settings/account/sessions/revoke-others",
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    # Caller's session still authenticates.
    me = client.get("/api/auth/me")
    assert me.status_code == 200

    # The other session is gone. Same TestClient cookie-jar workaround as the
    # password tests: clear the jar and pin to the target token before asserting.
    client.cookies.clear()
    client.cookies.set(_settings.session_cookie_name, other)
    me_other = client.get("/api/auth/me")
    assert me_other.status_code == 401


def test_sessions_revoke_others_requires_csrf_header(app_with_test_db, client):
    client, _ = _login(app_with_test_db, client)
    r = client.post("/api/settings/account/sessions/revoke-others")
    assert r.status_code == 403


def test_mask_token_is_unit_testable():
    # Verify the helper directly (it's small but worth covering both branches).
    from tradingagents_web.api.account import _mask_token
    assert _mask_token("abcd") == "***"
    assert _mask_token("abcdefgh") == "***"  # exactly 8 → mask
    long = "abcd1234ZZZZwxyz"
    out = _mask_token(long)
    assert out.startswith("abcd") and out.endswith("wxyz")
    assert "…" in out
