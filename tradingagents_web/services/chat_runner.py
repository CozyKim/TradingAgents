"""LangChain 1.x create_agent 기반 채팅 turn 실행 + SSE 발행."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain.agents.middleware import SummarizationMiddleware

from tradingagents.llm_clients import create_llm_client
from tradingagents_web.models import Analysis
from tradingagents_web.services.chat_context import KO_SUMMARY_PROMPT


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


# 모듈 상수 — § 12.3 Spec
CHAT_TURN_WINDOW = 8
SUMMARY_TRIGGER_FRACTION = 0.7
SUMMARY_KEEP_MESSAGES = 12


def resolve_chat_model(analysis: Analysis) -> Any:
    """분석 시 deep 모델 그대로 BaseChatModel 인스턴스로 변환.

    Args:
        analysis: Analysis 행.

    Returns:
        LangChain BaseChatModel 인스턴스.
    """
    client = create_llm_client(provider=analysis.llm_provider, model=analysis.llm_deep_model)
    return client.get_llm()


def summarization_middleware(analysis: Analysis) -> SummarizationMiddleware:
    """분석 quick 모델로 컨텍스트 요약 미들웨어를 빌드.

    Args:
        analysis: Analysis 행.

    Returns:
        SummarizationMiddleware 인스턴스 (trigger=fraction 0.7, keep=messages 12).
    """
    quick = create_llm_client(provider=analysis.llm_provider, model=analysis.llm_quick_model)
    return SummarizationMiddleware(
        model=quick.get_llm(),
        trigger=("fraction", SUMMARY_TRIGGER_FRACTION),
        keep=("messages", SUMMARY_KEEP_MESSAGES),
        summary_prompt=KO_SUMMARY_PROMPT,
    )
