"""chat_runner 단위 테스트 (외부 LLM 없이 stub)."""
import asyncio
import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from langchain.messages import AIMessageChunk

from tradingagents_web.models import Analysis, ChatMessage
from tradingagents_web.services.chat_runner import (
    ChatEvent,
    _execute_turn,
    chat_channel,
    resolve_chat_model,
    summarization_middleware,
)


def test_chat_event_dataclass_basic():
    ev = ChatEvent(type="token", data={"text": "hi"})
    assert ev.type == "token"
    assert ev.data == {"text": "hi"}


def test_chat_channel_format():
    assert chat_channel("run-1", "turn-1") == "chat:run-1:turn-1"


def _analysis() -> Analysis:
    return Analysis(
        run_id="r-x",
        ticker="AAPL",
        analysis_date=date(2026, 5, 8),
        status="completed",
        llm_provider="openai",
        llm_deep_model="gpt-5",
        llm_quick_model="gpt-5-mini",
        debate_rounds=1,
        analysts=["market"],
    )


def test_resolve_chat_model_uses_deep_model():
    with patch("tradingagents_web.services.chat_runner.create_llm_client") as mk:
        client = MagicMock()
        client.get_llm.return_value = "fake-llm"
        mk.return_value = client
        model = resolve_chat_model(_analysis())
        mk.assert_called_once_with(provider="openai", model="gpt-5")
        assert model == "fake-llm"


def test_summarization_middleware_uses_quick_model():
    with patch("tradingagents_web.services.chat_runner.create_llm_client") as mk, \
         patch("tradingagents_web.services.chat_runner.SummarizationMiddleware") as smw:
        client = MagicMock()
        client.get_llm.return_value = "fake-quick"
        mk.return_value = client
        summarization_middleware(_analysis())
        mk.assert_called_once_with(provider="openai", model="gpt-5-mini")
        kwargs = smw.call_args.kwargs
        assert kwargs["trigger"] == ("fraction", 0.7)
        assert kwargs["keep"] == ("messages", 12)


# ---------------------------------------------------------------------------
# _execute_turn 테스트 (stub agent)
# ---------------------------------------------------------------------------


def _persist_completed(db):
    a = _analysis()
    a.run_id = "r-exec-" + uuid.uuid4().hex[:6]
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _add_user_msg(db, analysis_id, seq, text):
    m = ChatMessage(
        analysis_id=analysis_id,
        turn_id="seed",
        sequence=seq,
        role="user",
        content_blocks=[{"type": "text", "text": text}],
    )
    db.add(m)
    db.commit()


class _FakeAgent:
    """`create_agent` 반환값을 흉내내는 stub."""

    def __init__(self, chunks):
        self._chunks = chunks

    async def astream(self, *_args, **_kwargs):
        for c in self._chunks:
            yield c


def _make_session_factory(db_session):
    """테스트 세션을 반환하되 close()를 no-op으로 패치한 factory를 반환한다."""

    def _no_close():
        pass  # 테스트 세션은 conftest가 관리하므로 닫지 않는다

    db_session.close = _no_close
    return lambda: db_session


@pytest.mark.asyncio
async def test_execute_turn_simple_text(db_session, monkeypatch):
    a = _persist_completed(db_session)
    _add_user_msg(db_session, a.id, 0, "안녕")
    chunk = (AIMessageChunk(content="안녕하세요"), {})
    agent = _FakeAgent([{"type": "messages", "data": chunk}])
    monkeypatch.setattr(
        "tradingagents_web.services.chat_runner._build_agent",
        lambda *_: agent,
    )
    monkeypatch.setattr(
        "tradingagents_web.services.chat_runner._session_factory",
        _make_session_factory(db_session),
    )

    await _execute_turn(run_id=a.run_id, analysis_id=a.id, turn_id="t-1")

    saved = (
        db_session.query(ChatMessage)
        .filter_by(turn_id="t-1", role="assistant")
        .one()
    )
    assert saved.partial is False
    assert saved.cancelled is False
    text = "".join(b.get("text", "") for b in saved.content_blocks if b.get("type") == "text")
    assert "안녕하세요" in text


@pytest.mark.asyncio
async def test_execute_turn_runtime_error_persists_partial(db_session, monkeypatch):
    a = _persist_completed(db_session)
    _add_user_msg(db_session, a.id, 0, "안녕")

    class _Boom:
        async def astream(self, *_args, **_kwargs):
            yield {"type": "messages", "data": (AIMessageChunk(content="중간"), {})}
            raise RuntimeError("provider down")

    monkeypatch.setattr(
        "tradingagents_web.services.chat_runner._build_agent",
        lambda *_: _Boom(),
    )
    monkeypatch.setattr(
        "tradingagents_web.services.chat_runner._session_factory",
        _make_session_factory(db_session),
    )

    await _execute_turn(run_id=a.run_id, analysis_id=a.id, turn_id="t-2")

    saved = (
        db_session.query(ChatMessage)
        .filter_by(turn_id="t-2", role="assistant")
        .one()
    )
    assert saved.partial is True
    assert saved.error == "provider down"
    text = "".join(b.get("text", "") for b in saved.content_blocks if b.get("type") == "text")
    assert "중간" in text


@pytest.mark.asyncio
async def test_execute_turn_cancellation_persists_cancelled(db_session, monkeypatch):
    a = _persist_completed(db_session)
    _add_user_msg(db_session, a.id, 0, "긴 질문")

    class _Slow:
        async def astream(self, *_args, **_kwargs):
            yield {"type": "messages", "data": (AIMessageChunk(content="짧은"), {})}
            await asyncio.sleep(10)
            yield None  # never reached

    monkeypatch.setattr(
        "tradingagents_web.services.chat_runner._build_agent",
        lambda *_: _Slow(),
    )
    monkeypatch.setattr(
        "tradingagents_web.services.chat_runner._session_factory",
        _make_session_factory(db_session),
    )

    task = asyncio.create_task(
        _execute_turn(run_id=a.run_id, analysis_id=a.id, turn_id="t-3")
    )
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    saved = (
        db_session.query(ChatMessage)
        .filter_by(turn_id="t-3", role="assistant")
        .one()
    )
    assert saved.cancelled is True
    assert saved.partial is True
    assert saved.error is None
