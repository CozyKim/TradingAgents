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
