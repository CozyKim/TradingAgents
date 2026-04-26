"""Tests for Schedule ORM model + Analysis.schedule_id FK."""
from datetime import date

from tradingagents_web.models import Analysis, Schedule


def test_schedule_minimal_fields(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        s = Schedule(
            name="AAPL daily",
            ticker="AAPL",
            cron_expr="30 16 * * 1-5",
            preset={"analysts": ["market"], "debate_rounds": 1},
            active=True,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        assert s.id > 0
        assert s.last_run is None
        assert s.next_run is None
        assert s.created_at is not None
    finally:
        db.close()


def test_analysis_schedule_id_fk(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        s = Schedule(name="x", ticker="X", cron_expr="0 9 * * *", preset={}, active=True)
        db.add(s)
        db.commit()
        a = Analysis(
            run_id="00000000-0000-0000-0000-000000000099",
            ticker="X",
            analysis_date=date(2026, 4, 25),
            status="running",
            llm_provider="openai",
            llm_deep_model="gpt-5.5",
            llm_quick_model="gpt-5.4-mini",
            debate_rounds=1,
            analysts=["market"],
            schedule_id=s.id,
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        assert a.schedule_id == s.id
    finally:
        db.close()
