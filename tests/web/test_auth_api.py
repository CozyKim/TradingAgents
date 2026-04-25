from fastapi.testclient import TestClient

from tradingagents_web.auth import hash_password
from tradingagents_web.models import User

XHR = {"X-Requested-With": "fetch"}


def _seed_user(SessionLocal, password: str) -> None:
    with SessionLocal() as db:
        db.add(User(password_hash=hash_password(password)))
        db.commit()


def test_login_with_correct_password_sets_cookie(app_with_test_db) -> None:
    app, SessionLocal = app_with_test_db
    _seed_user(SessionLocal, "hunter2")
    client = TestClient(app)

    response = client.post("/api/auth/login", json={"password": "hunter2"}, headers=XHR)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert "tradingagents_session" in response.cookies


def test_login_with_wrong_password_returns_401(app_with_test_db) -> None:
    app, SessionLocal = app_with_test_db
    _seed_user(SessionLocal, "hunter2")
    client = TestClient(app)

    response = client.post("/api/auth/login", json={"password": "wrong"}, headers=XHR)
    assert response.status_code == 401


def test_login_when_no_user_returns_503(app_with_test_db) -> None:
    app, _SessionLocal = app_with_test_db
    client = TestClient(app)

    response = client.post("/api/auth/login", json={"password": "anything"}, headers=XHR)
    assert response.status_code == 503


def test_me_requires_auth(app_with_test_db) -> None:
    app, _SessionLocal = app_with_test_db
    client = TestClient(app)
    assert client.get("/api/auth/me").status_code == 401


def test_full_flow_login_me_logout(app_with_test_db) -> None:
    app, SessionLocal = app_with_test_db
    _seed_user(SessionLocal, "hunter2")
    client = TestClient(app)

    client.post("/api/auth/login", json={"password": "hunter2"}, headers=XHR)
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"id": 1}

    client.post("/api/auth/logout", headers=XHR)
    assert client.get("/api/auth/me").status_code == 401


def test_login_without_xhr_header_returns_403(app_with_test_db) -> None:
    """Missing X-Requested-With header → CSRF check rejects the request."""
    app, SessionLocal = app_with_test_db
    _seed_user(SessionLocal, "hunter2")
    client = TestClient(app)

    response = client.post("/api/auth/login", json={"password": "hunter2"})
    assert response.status_code == 403


def test_logout_without_xhr_header_returns_403(app_with_test_db) -> None:
    app, _SessionLocal = app_with_test_db
    client = TestClient(app)
    response = client.post("/api/auth/logout")
    assert response.status_code == 403


def test_authenticated_request_keeps_cookie(app_with_test_db) -> None:
    """Subsequent authenticated requests should not drop the session cookie
    (sliding refresh middleware re-issues it)."""
    app, SessionLocal = app_with_test_db
    _seed_user(SessionLocal, "hunter2")
    client = TestClient(app)

    client.post("/api/auth/login", json={"password": "hunter2"}, headers=XHR)
    initial = client.cookies.get("tradingagents_session")
    assert initial is not None

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    # cookie still present and unchanged
    assert client.cookies.get("tradingagents_session") == initial
