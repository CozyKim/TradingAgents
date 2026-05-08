"""chat_runner 단위 테스트 (외부 LLM 없이 stub)."""
from datetime import date
from unittest.mock import MagicMock, patch

from tradingagents_web.models import Analysis
from tradingagents_web.services.chat_runner import (
    ChatEvent,
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
