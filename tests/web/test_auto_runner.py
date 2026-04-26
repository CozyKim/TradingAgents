"""Tests for services.auto_runner.trigger_run."""
import pytest

from tradingagents_web.models import Analysis, Schedule
from tradingagents_web.services.auto_runner import trigger_run
from tradingagents_web.services.event_bus import reset_event_bus


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_event_bus()
    yield
    reset_event_bus()


@pytest.mark.asyncio
async def test_trigger_run_creates_analysis_row_and_updates_schedule(
    monkeypatch, app_with_test_db
):
    monkeypatch.setenv("WEB_FAKE_RUNNER", "true")
    monkeypatch.setenv("WEB_FAKE_RUNNER_DELAY_SECONDS", "0")

    _, TestSessionLocal = app_with_test_db
    from tradingagents_web.api import runs as runs_api
    runs_api.set_background_session_factory(TestSessionLocal)

    db = TestSessionLocal()
    try:
        sched = Schedule(
            name="auto",
            ticker="AAPL",
            cron_expr="0 9 * * *",
            preset={"analysts": ["market", "news"], "debate_rounds": 1},
            active=True,
        )
        db.add(sched)
        db.commit()
        db.refresh(sched)
        sid = sched.id
    finally:
        db.close()

    await trigger_run(sid, session_factory=TestSessionLocal)

    db = TestSessionLocal()
    try:
        rows = db.query(Analysis).filter_by(schedule_id=sid).all()
        assert len(rows) == 1
        assert rows[0].ticker == "AAPL"
        assert rows[0].status in ("running", "completed")
        sched = db.query(Schedule).get(sid)
        assert sched.last_run is not None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_trigger_run_dispatches_schedule_failure_on_exception(
    app_with_test_db, monkeypatch
):
    """If start_analysis_run raises, trigger_run must dispatch schedule_failure."""
    from unittest.mock import AsyncMock

    from tradingagents_web.api import runs as runs_api
    from tradingagents_web.models import Schedule
    from tradingagents_web.services import auto_runner, notifier

    spy = AsyncMock()
    monkeypatch.setattr(notifier, "dispatch_schedule_failure", spy)

    def boom(*a, **kw):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(runs_api, "start_analysis_run", boom)

    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        sched = Schedule(
            name="t",
            ticker="AAPL",
            cron_expr="0 9 * * 1-5",
            preset={},
            active=True,
            source="user",
        )
        db.add(sched)
        db.commit()
        db.refresh(sched)
        sched_id = sched.id
    finally:
        db.close()

    result = await auto_runner.trigger_run(sched_id, session_factory=TestSessionLocal)

    assert result is None
    spy.assert_awaited_once()
    kwargs = spy.await_args.kwargs
    assert kwargs["schedule_id"] == sched_id
    assert kwargs["ticker"] == "AAPL"
    assert "connection refused" in kwargs["error"]
