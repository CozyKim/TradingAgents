"""채팅에 노출되는 도구 묶음 회귀 테스트."""
from tradingagents_web.services.chat_tools import CHAT_TOOLS, get_chat_tools


def test_chat_tools_are_nine():
    assert len(CHAT_TOOLS) == 9


def test_chat_tools_have_unique_names():
    names = [t.name for t in CHAT_TOOLS]
    assert len(set(names)) == 9


def test_get_chat_tools_returns_list():
    tools = get_chat_tools(analysis=None)
    assert tools == CHAT_TOOLS
