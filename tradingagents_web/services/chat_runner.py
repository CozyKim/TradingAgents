"""LangChain 1.x create_agent 기반 채팅 turn 실행 + SSE 발행."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ChatEvent:
    """채팅 SSE 이벤트 한 단위.

    Attributes:
        type: token|tool_call|tool_result|done|error|cancelled|close 중 하나.
        data: 이벤트 페이로드.
    """

    type: str
    data: dict[str, Any]


def chat_channel(run_id: str, turn_id: str) -> str:
    """event_bus 채널 키 ("chat:{run_id}:{turn_id}")를 반환."""
    return f"chat:{run_id}:{turn_id}"
