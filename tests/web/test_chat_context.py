"""chat_context 빌더 회귀 테스트."""
import uuid
from datetime import date

from langchain.messages import AIMessage, HumanMessage, ToolMessage

from tradingagents_web.models import Analysis, ChatMessage
from tradingagents_web.services.chat_context import build_message_history, build_system_prompt


def _analysis(final_state: dict | None = None, decision="BUY", confidence=0.7) -> Analysis:
    return Analysis(
        run_id="r-x",
        ticker="AAPL",
        analysis_date=date(2026, 5, 8),
        status="completed",
        decision=decision,
        confidence=confidence,
        llm_provider="openai",
        llm_deep_model="gpt-5",
        llm_quick_model="gpt-5-mini",
        debate_rounds=1,
        analysts=["market"],
        final_state=final_state or {},
    )


def _persist_analysis(db_session) -> Analysis:
    a = _analysis()
    a.run_id = "r-history-" + uuid.uuid4().hex[:6]
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a


def _add_turn(db, analysis_id, seq_start, user_text, ai_text, *, partial=False):
    tid = str(uuid.uuid4())
    db.add(ChatMessage(
        analysis_id=analysis_id, turn_id=tid, sequence=seq_start,
        role="user", content_blocks=[{"type": "text", "text": user_text}],
    ))
    db.add(ChatMessage(
        analysis_id=analysis_id, turn_id=tid, sequence=seq_start + 1,
        role="assistant", content_blocks=[{"type": "text", "text": ai_text}],
        partial=partial,
    ))
    db.commit()
    return tid


def test_system_prompt_includes_meta():
    prompt = build_system_prompt(_analysis())
    assert "AAPL" in prompt
    assert "2026-05-08" in prompt
    assert "BUY" in prompt
    assert "gpt-5" in prompt


def test_system_prompt_omits_empty_sections():
    prompt = build_system_prompt(_analysis(final_state={}))
    assert "📈 시장 분석" not in prompt


def test_history_returns_langchain_messages(db_session):
    a = _persist_analysis(db_session)
    _add_turn(db_session, a.id, 0, "안녕", "안녕하세요")
    msgs = build_message_history(db_session, a.id, window_n=8)
    assert isinstance(msgs[0], HumanMessage)
    assert isinstance(msgs[1], AIMessage)
    assert msgs[0].content == [{"type": "text", "text": "안녕"}]


def test_history_sliding_window_keeps_last_n_turns(db_session):
    a = _persist_analysis(db_session)
    seq = 0
    for i in range(10):
        _add_turn(db_session, a.id, seq, f"q{i}", f"a{i}")
        seq += 2
    msgs = build_message_history(db_session, a.id, window_n=3)
    # 3 turns × 2 messages = 6
    assert len(msgs) == 6
    user_texts = [m.content[0]["text"] for m in msgs if isinstance(m, HumanMessage)]
    assert user_texts == ["q7", "q8", "q9"]


def test_history_includes_partial_assistant(db_session):
    a = _persist_analysis(db_session)
    _add_turn(db_session, a.id, 0, "끊긴 질문", "끊긴 답", partial=True)
    msgs = build_message_history(db_session, a.id, window_n=8)
    assert len(msgs) == 2


def test_system_prompt_includes_filled_sections():
    fs = {"market_report": "AAPL은 상승 추세", "fundamentals_report": "PE 28"}
    prompt = build_system_prompt(_analysis(final_state=fs))
    assert "📈 시장 분석" in prompt
    assert "AAPL은 상승 추세" in prompt
    assert "📊 펀더멘털" in prompt
    assert "PE 28" in prompt
