"""Sanity check: app lifespan starts/stops the scheduler cleanly."""
import pytest
from fastapi.testclient import TestClient

from tradingagents_web.main import create_app
from tradingagents_web.services import scheduler as scheduler_module


def test_lifespan_starts_scheduler():
    app = create_app()
    with TestClient(app) as client:
        # When the TestClient context is open, lifespan startup has finished.
        svc = scheduler_module.get_scheduler()
        assert svc.is_running()
        r = client.get("/api/health")
        assert r.status_code == 200
    # On exit, lifespan shutdown runs.
    with pytest.raises(RuntimeError):
        scheduler_module.get_scheduler()
