"""End-to-end backend test simulating the M1 happy path.

Covers: no-user-yet → set-password CLI → login → /me → logout.
"""
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradingagents_web.auth import hash_password
from tradingagents_web.db import get_db
from tradingagents_web.main import create_app
from tradingagents_web.models import Base, User


@pytest.fixture()
def client(tmp_path) -> Generator[TestClient, None, None]:
    db_file = tmp_path / "m1.db"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override

    # Seed user (simulating CLI set-password)
    with TestSessionLocal() as db:
        db.add(User(password_hash=hash_password("hunter2")))
        db.commit()

    yield TestClient(app)


def test_m1_happy_path(client: TestClient) -> None:
    # 1. /me before login → 401
    assert client.get("/api/auth/me").status_code == 401

    # 2. Login
    r = client.post("/api/auth/login", json={"password": "hunter2"})
    assert r.status_code == 200

    # 3. /me succeeds
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"id": 1}

    # 4. Logout
    out = client.post("/api/auth/logout")
    assert out.status_code == 200

    # 5. /me again → 401
    assert client.get("/api/auth/me").status_code == 401


def test_m1_invalid_password_returns_401(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"password": "wrong"})
    assert r.status_code == 401
