"""Tests for SchedulerService."""
import asyncio
from datetime import datetime, timezone

import pytest

from tradingagents_web.models import Schedule
from tradingagents_web.services.scheduler import SchedulerService


@pytest.fixture()
def svc():
    s = SchedulerService(tz="UTC")
    yield s
    if s.is_running():
        s.shutdown()


def test_start_and_shutdown(svc):
    svc.start()
    assert svc.is_running() is True
    svc.shutdown()
    assert svc.is_running() is False


def test_register_schedule_creates_apjob(svc, app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        sched = Schedule(
            name="d",
            ticker="AAPL",
            cron_expr="0 9 * * *",
            preset={"analysts": ["market"], "debate_rounds": 1},
            active=True,
        )
        db.add(sched)
        db.commit()
        db.refresh(sched)
    finally:
        db.close()

    triggered: list[int] = []

    async def fake_trigger(schedule_id: int) -> None:
        triggered.append(schedule_id)

    svc.set_trigger_callback(fake_trigger)
    svc.start()
    svc.register(sched)
    job = svc.get_job(sched.id)
    assert job is not None
    assert job.next_run_time is not None


def test_unregister_drops_apjob(svc):
    svc.start()
    sched = type("S", (), {"id": 99, "cron_expr": "0 9 * * *", "active": True})()
    # Manually add a noop job to exercise unregister path
    svc.scheduler.add_job(lambda: None, "cron", id=svc._job_id(99), minute=0, hour=9)
    svc.unregister(99)
    assert svc.get_job(99) is None
