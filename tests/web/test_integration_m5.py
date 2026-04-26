"""End-to-end M5 polish: backup → mutate → restore round-trip."""
from __future__ import annotations

import io

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
    finally:
        db.close()
    client.cookies.set(_settings.session_cookie_name, token)
    return client


def test_backup_then_restore_roundtrip(app_with_test_db, client):
    client = _login(app_with_test_db, client)

    # 1. Capture a backup of the live (test) DB.
    r = client.get("/api/settings/account/backup")
    assert r.status_code == 200, r.text
    backup_bytes = r.content
    assert backup_bytes.startswith(b"SQLite format 3\x00")

    # 2. Mutate state — change the password.
    r = client.put(
        "/api/settings/account/password",
        json={
            "current_password": "testpass",
            "new_password": "newpass1234",
            "revoke_other_sessions": False,
        },
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200, r.text

    # New password authenticates.
    r = client.post(
        "/api/auth/login",
        json={"password": "newpass1234"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200

    # 3. Restore the original backup. Must POST as multipart with CSRF header.
    r = client.post(
        "/api/settings/account/restore",
        files={"file": ("backup.db", io.BytesIO(backup_bytes), "application/octet-stream")},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # 4. Old password works again — proves the restore really replaced the DB.
    # Clear the cookie jar first because the prior login + restore may have
    # left stale Set-Cookie state in the client.
    client.cookies.clear()
    r = client.post(
        "/api/auth/login",
        json={"password": "testpass"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 200, "Original password should authenticate after restore"

    # 5. New password no longer works.
    client.cookies.clear()
    r = client.post(
        "/api/auth/login",
        json={"password": "newpass1234"},
        headers={"X-Requested-With": "fetch"},
    )
    assert r.status_code == 401, "Mutated password should NOT authenticate after restore"
