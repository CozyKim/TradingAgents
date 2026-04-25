"""Shared fixtures for web tests."""
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tradingagents_web.db import get_db
from tradingagents_web.models import Base


@pytest.fixture()
def app_with_test_db(tmp_path: Path):
    """Build a FastAPI app whose DB dependency points at a fresh sqlite file."""
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
    return app, TestSessionLocal


@pytest.fixture()
def client(app_with_test_db) -> TestClient:
    app, _ = app_with_test_db
    return TestClient(app)
