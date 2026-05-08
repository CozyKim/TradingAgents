"""chat_runner 단위 테스트 (외부 LLM 없이 stub)."""
from tradingagents_web.services.chat_runner import (
    ChatEvent,
    chat_channel,
)


def test_chat_event_dataclass_basic():
    ev = ChatEvent(type="token", data={"text": "hi"})
    assert ev.type == "token"
    assert ev.data == {"text": "hi"}


def test_chat_channel_format():
    assert chat_channel("run-1", "turn-1") == "chat:run-1:turn-1"
