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


def _make_full_schema_db(path):
    """Create a SQLite file with all required tables (empty).

    Mirrors ``_REQUIRED_TABLES`` in tradingagents_web/api/account.py — when
    that list grows (M6 added sectors/sector_runs/sector_reports) this
    fixture must grow with it so restore validation passes.
    """
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(path)
    conn.executescript(
        '''
        CREATE TABLE users (id INTEGER PRIMARY KEY, password_hash TEXT, created_at TEXT);
        CREATE TABLE sessions (id TEXT PRIMARY KEY, user_id INTEGER, expires_at TEXT, created_at TEXT);
        CREATE TABLE analyses (id INTEGER PRIMARY KEY);
        CREATE TABLE holdings (id INTEGER PRIMARY KEY);
        CREATE TABLE schedules (id INTEGER PRIMARY KEY);
        CREATE TABLE alerts (id INTEGER PRIMARY KEY);
        CREATE TABLE settings (key TEXT PRIMARY KEY);
        CREATE TABLE sectors (id INTEGER PRIMARY KEY);
        CREATE TABLE sector_runs (id TEXT PRIMARY KEY);
        CREATE TABLE sector_reports (id INTEGER PRIMARY KEY);
        '''
    )
    conn.commit()
    conn.close()


def test_restore_replaces_database_with_uploaded_file(app_with_test_db, client, tmp_path):
    client, _ = _login(app_with_test_db, client)
    new_db = tmp_path / "incoming.db"
    _make_full_schema_db(new_db)

    with new_db.open("rb") as fh:
        r = client.post(
            "/api/settings/account/restore",
            files={"file": ("backup.db", fh, "application/octet-stream")},
            headers={"X-Requested-With": "fetch"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["detail"]

    # The caller's session no longer exists in the new (empty) sessions table.
    me = client.get("/api/auth/me")
    assert me.status_code == 401


def test_restore_rejects_garbage_file(app_with_test_db, client):
    client, _ = _login(app_with_test_db, client)
    r = client.post(
        "/api/settings/account/restore",
        files={"file": ("bad.db", b"not a sqlite file", "application/octet-stream")},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 400


def test_restore_rejects_db_missing_required_tables(app_with_test_db, client, tmp_path):
    client, _ = _login(app_with_test_db, client)
    incomplete = tmp_path / "partial.db"
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(incomplete)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, password_hash TEXT)")
    conn.commit()
    conn.close()

    with incomplete.open("rb") as fh:
        r = client.post(
            "/api/settings/account/restore",
            files={"file": ("partial.db", fh, "application/octet-stream")},
            headers={"X-Requested-With": "fetch"},
        )
    assert r.status_code == 400
    detail = r.json()["detail"]
    # Should name at least one missing required table
    assert any(t in detail for t in ("sessions", "analyses", "holdings", "schedules", "alerts", "settings"))


def test_restore_requires_csrf_header(app_with_test_db, client, tmp_path):
    client, _ = _login(app_with_test_db, client)
    new_db = tmp_path / "incoming.db"
    _make_full_schema_db(new_db)
    with new_db.open("rb") as fh:
        r = client.post(
            "/api/settings/account/restore",
            files={"file": ("backup.db", fh, "application/octet-stream")},
        )
    assert r.status_code == 403


def test_restore_requires_auth(client, tmp_path):
    new_db = tmp_path / "incoming.db"
    _make_full_schema_db(new_db)
    with new_db.open("rb") as fh:
        r = client.post(
            "/api/settings/account/restore",
            files={"file": ("backup.db", fh, "application/octet-stream")},
            headers={"X-Requested-With": "fetch"},
        )
    assert r.status_code == 401
