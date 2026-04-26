"""Tests for Analysis ORM model."""
from datetime import date, datetime, timezone

from tradingagents_web.models import Analysis


def test_analysis_minimal_fields(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        a = Analysis(
            run_id="00000000-0000-0000-0000-000000000001",
            ticker="AAPL",
            analysis_date=date(2026, 4, 25),
            status="running",
            llm_provider="openai",
            llm_deep_model="gpt-5.5",
            llm_quick_model="gpt-5.4-mini",
            debate_rounds=1,
            analysts=["market", "news", "fundamentals", "social"],
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        assert a.id > 0
        assert a.created_at is not None
        assert a.completed_at is None
        assert a.decision is None
        assert a.final_state is None
    finally:
        db.close()


def test_analysis_completed_with_state(app_with_test_db):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        a = Analysis(
            run_id="00000000-0000-0000-0000-000000000002",
            ticker="NVDA",
            analysis_date=date(2026, 4, 25),
            status="completed",
            decision="BUY",
            confidence=0.78,
            llm_provider="openai",
            llm_deep_model="gpt-5.5",
            llm_quick_model="gpt-5.4-mini",
            debate_rounds=1,
            analysts=["market"],
            final_state={"market_report": "..."},
            completed_at=datetime.now(timezone.utc),
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        assert a.decision == "BUY"
        assert a.final_state["market_report"] == "..."
    finally:
        db.close()
