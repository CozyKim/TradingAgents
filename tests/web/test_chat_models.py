"""ChatMessage ORM 회귀 테스트."""
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from tradingagents_web.models import Analysis, ChatMessage


def _make_analysis(db_session) -> Analysis:
    a = Analysis(
        run_id="r-chat-1",
        ticker="AAPL",
        analysis_date=date(2026, 5, 8),
        status="completed",
        llm_provider="openai",
        llm_deep_model="gpt-5",
        llm_quick_model="gpt-5-mini",
        debate_rounds=1,
        analysts=["market"],
    )
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


def test_insert_user_message_round_trip(db_session):
    a = _make_analysis(db_session)
    msg = ChatMessage(
        analysis_id=a.id,
        turn_id="t-1",
        sequence=0,
        role="user",
        content_blocks=[{"type": "text", "text": "안녕"}],
    )
    db_session.add(msg)
    db_session.commit()
    out = db_session.query(ChatMessage).filter_by(id=msg.id).one()
    assert out.role == "user"
    assert out.content_blocks == [{"type": "text", "text": "안녕"}]
    assert out.partial is False and out.cancelled is False


def test_unique_analysis_sequence(db_session):
    a = _make_analysis(db_session)
    db_session.add_all([
        ChatMessage(
            analysis_id=a.id, turn_id="t-1", sequence=0,
            role="user", content_blocks=[],
        ),
        ChatMessage(
            analysis_id=a.id, turn_id="t-1", sequence=1,
            role="assistant", content_blocks=[],
        ),
    ])
    db_session.commit()

    db_session.add(ChatMessage(
        analysis_id=a.id, turn_id="t-2", sequence=1,
        role="user", content_blocks=[],
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
