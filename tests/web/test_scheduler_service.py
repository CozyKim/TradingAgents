"""Tests for SchedulerService.

Tests run inside pytest-asyncio's auto-mode loop because
``AsyncIOScheduler.start()`` requires a running event loop. Shutdown
defers state mutation to ``call_soon_threadsafe``, so we yield to the
loop a couple of times before asserting on ``is_running()``.
"""
import asyncio

import pytest_asyncio

from tradingagents_web.models import Schedule
from tradingagents_web.services.scheduler import SchedulerService


async def _yield_loop(times: int = 3) -> None:
    for _ in range(times):
        await asyncio.sleep(0)


@pytest_asyncio.fixture()
async def svc():
    s = SchedulerService(tz="UTC")
    try:
        yield s
    finally:
        if s.is_running():
            s.shutdown()
            await _yield_loop()


async def test_start_and_shutdown(svc):
    svc.start()
    assert svc.is_running() is True
    svc.shutdown()
    await _yield_loop()
    assert svc.is_running() is False


async def test_register_schedule_creates_apjob(svc, app_with_test_db):
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


async def test_unregister_drops_apjob(svc):
    svc.start()
    svc.scheduler.add_job(lambda: None, "cron", id=svc._job_id(99), minute=0, hour=9)
    svc.unregister(99)
    assert svc.get_job(99) is None
