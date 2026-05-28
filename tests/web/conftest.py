"""Shared fixtures for web tests."""
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.db import SessionLocal as ProdSessionLocal
from tradingagents_web.db import get_db
from tradingagents_web.models import Base, User

_settings = Settings()


@pytest.fixture()
def app_with_test_db(tmp_path: Path):
    """Build a FastAPI app whose DB dependency points at a fresh sqlite file.

    Also overrides the background-task session factory so that
    _execute_and_persist writes to the same test DB, not the production one.
    Restores the production factory on teardown.
    """
    from tradingagents_web.api import runs as runs_api
    from tradingagents_web.api import sectors as sectors_api
    from tradingagents_web.main import create_app

    db_file = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override_get_db() -> Generator:
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override_get_db
    runs_api.set_background_session_factory(TestSessionLocal)
    sectors_api.set_background_session_factory(TestSessionLocal)
    try:
        yield app, TestSessionLocal
    finally:
        runs_api.set_background_session_factory(ProdSessionLocal)
        sectors_api.set_background_session_factory(ProdSessionLocal)


@pytest.fixture()
def client(app_with_test_db) -> TestClient:
    """인증 없는 TestClient (기존 동작 유지)."""
    app, _ = app_with_test_db
    return TestClient(app)


@pytest.fixture()
def client_unauth(app_with_test_db) -> TestClient:
    """인증 없는 TestClient (명시적 미인증)."""
    app, _ = app_with_test_db
    return TestClient(app)


@pytest.fixture()
def auth_client(app_with_test_db) -> TestClient:
    """세션 쿠키가 설정된 인증 TestClient."""
    app, TestSessionLocal = app_with_test_db
    tc = TestClient(app)
    db = TestSessionLocal()
    try:
        user = User(password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
    finally:
        db.close()
    tc.cookies.set(_settings.session_cookie_name, token)
    return tc


@pytest.fixture()
def db_session(app_with_test_db):
    """Provide a clean database session for each test."""
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
