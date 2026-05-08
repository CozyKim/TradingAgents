"""LangChain 1.x create_agent 기반 채팅 turn 실행 + SSE 발행."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain.messages import AIMessage, AIMessageChunk, ToolMessage
from sqlalchemy.orm import Session as OrmSession

from tradingagents.llm_clients import create_llm_client
from tradingagents_web.db import SessionLocal
from tradingagents_web.models import Analysis, ChatMessage
from tradingagents_web.services.chat_context import (
    KO_SUMMARY_PROMPT,
    build_message_history,
    build_system_prompt,
)
from tradingagents_web.services.chat_tools import get_chat_tools
from tradingagents_web.services.event_bus import AnalysisEvent, get_event_bus

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# _execute_turn 내부 헬퍼
# ---------------------------------------------------------------------------

_session_factory = SessionLocal
_RUNNING_TURNS: dict[str, "asyncio.Task[None]"] = {}


def _build_agent(analysis: Analysis) -> Any:
    """LangChain 1.x agent 인스턴스 — 테스트에서 monkeypatch 대상.

    Args:
        analysis: Analysis 행.

    Returns:
        create_agent 반환 객체 (astream 메서드 보유).
    """
    return create_agent(
        model=resolve_chat_model(analysis),
        tools=get_chat_tools(analysis),
        system_prompt=build_system_prompt(analysis),
        middleware=[summarization_middleware(analysis)],
    )


def _next_sequence(db: OrmSession, analysis_id: int) -> int:
    """분석의 다음 sequence 번호를 반환한다.

    Args:
        db: DB 세션.
        analysis_id: 분석 ID.

    Returns:
        현재 최대 sequence + 1 (없으면 0).
    """
    last = (
        db.query(ChatMessage.sequence)
        .filter_by(analysis_id=analysis_id)
        .order_by(ChatMessage.sequence.desc())
        .first()
    )
    return (last[0] + 1) if last else 0


def _persist_assistant(
    db: OrmSession,
    *,
    analysis_id: int,
    turn_id: str,
    content_blocks: list[Any],
    tool_calls: list[Any] | None,
    model_id: str | None,
    cost_usd: float | None,
    partial: bool,
    cancelled: bool,
    error: str | None,
) -> ChatMessage:
    """assistant 메시지를 DB에 영속화한다.

    Args:
        db: DB 세션.
        analysis_id: 분석 ID.
        turn_id: 턴 UUID.
        content_blocks: 콘텐츠 블록 리스트.
        tool_calls: 도구 호출 리스트 (없으면 None).
        model_id: 사용 모델 ID.
        cost_usd: 비용 (USD).
        partial: 부분 완료 여부.
        cancelled: 취소 여부.
        error: 에러 메시지 (없으면 None).

    Returns:
        저장된 ChatMessage 행.
    """
    seq = _next_sequence(db, analysis_id)
    row = ChatMessage(
        analysis_id=analysis_id,
        turn_id=turn_id,
        sequence=seq,
        role="assistant",
        content_blocks=content_blocks,
        tool_calls=tool_calls or None,
        partial=partial,
        cancelled=cancelled,
        error=error,
        model_id=model_id,
        cost_usd=cost_usd,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return row


def _persist_tool(
    db: OrmSession,
    *,
    analysis_id: int,
    turn_id: str,
    msg: ToolMessage,
) -> None:
    """tool 결과 메시지를 DB에 영속화한다.

    Args:
        db: DB 세션.
        analysis_id: 분석 ID.
        turn_id: 턴 UUID.
        msg: LangChain ToolMessage.
    """
    seq = _next_sequence(db, analysis_id)
    blocks: list[Any] = (
        msg.content
        if isinstance(msg.content, list)
        else [{"type": "text", "text": str(msg.content)}]
    )
    db.add(
        ChatMessage(
            analysis_id=analysis_id,
            turn_id=turn_id,
            sequence=seq,
            role="tool",
            content_blocks=blocks,
            tool_call_id=msg.tool_call_id,
            tool_name=msg.name,
            completed_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


async def _execute_turn(*, run_id: str, analysis_id: int, turn_id: str) -> None:
    """analysis의 turn을 백그라운드로 실행하며 SSE 이벤트를 발행한다.

    정상 종료: assistant 메시지 + 동반 tool 메시지 영속화 후 done 이벤트.
    예외 발생: 부분 누적분 partial=true 영속화 후 error 이벤트.
    CancelledError: 부분 누적분 cancelled=true 영속화 후 cancelled 이벤트, raise.
    어떤 경로에서든 close 이벤트 + finish.

    Args:
        run_id: 분석 run_id (UUID).
        analysis_id: ChatMessage 영속화에 쓰는 analyses.id.
        turn_id: 이번 turn의 UUID.
    """
    bus = get_event_bus()
    channel = chat_channel(run_id, turn_id)
    db = _session_factory()
    text_blocks: dict[int, str] = {}
    tool_calls_emitted: dict[str, Any] = {}
    pending_tool_messages: list[ToolMessage] = []
    final_message: AIMessage | None = None

    def _final_blocks() -> list[Any]:
        if final_message is not None and isinstance(final_message.content, list):
            return final_message.content
        if text_blocks:
            return [
                {"type": "text", "text": text_blocks[i]}
                for i in sorted(text_blocks)
            ]
        return []

    try:
        analysis = db.query(Analysis).filter_by(id=analysis_id).one()
        history = build_message_history(db, analysis_id, window_n=CHAT_TURN_WINDOW)
        agent = _build_agent(analysis)

        async for chunk in agent.astream(
            {"messages": history},
            stream_mode=["messages", "updates"],
            version="v2",
        ):
            ctype = chunk.get("type")
            data = chunk.get("data")
            if ctype == "messages":
                token, _ = data
                if isinstance(token, AIMessageChunk) and token.text:
                    bi = 0  # MVP: 단일 텍스트 블록
                    text_blocks[bi] = text_blocks.get(bi, "") + token.text
                    bus.publish(
                        channel,
                        AnalysisEvent(
                            type="token",
                            data={"text": token.text, "block_index": bi},
                        ),
                    )
            elif ctype == "updates":
                for source, update in data.items():
                    last = update["messages"][-1]
                    if source == "model" and isinstance(last, AIMessage):
                        final_message = last
                        for tc in last.tool_calls or []:
                            tc_id = tc.get("id")
                            if tc_id and tc_id not in tool_calls_emitted:
                                tool_calls_emitted[tc_id] = tc
                                bus.publish(
                                    channel,
                                    AnalysisEvent(
                                        type="tool_call",
                                        data={
                                            "id": tc_id,
                                            "name": tc.get("name", ""),
                                            "args": tc.get("args", {}),
                                        },
                                    ),
                                )
                    elif source == "tools" and isinstance(last, ToolMessage):
                        pending_tool_messages.append(last)
                        ok = (
                            not (last.status == "error")
                            if hasattr(last, "status")
                            else True
                        )
                        bus.publish(
                            channel,
                            AnalysisEvent(
                                type="tool_result",
                                data={
                                    "tool_call_id": last.tool_call_id,
                                    "name": last.name,
                                    "content_blocks": (
                                        last.content
                                        if isinstance(last.content, list)
                                        else [{"type": "text", "text": str(last.content)}]
                                    ),
                                    "ok": ok,
                                },
                            ),
                        )

        ai_row = _persist_assistant(
            db,
            analysis_id=analysis_id,
            turn_id=turn_id,
            content_blocks=_final_blocks(),
            tool_calls=(final_message.tool_calls if final_message else None),
            model_id=analysis.llm_deep_model,
            cost_usd=None,
            partial=False,
            cancelled=False,
            error=None,
        )
        for tm in pending_tool_messages:
            _persist_tool(db, analysis_id=analysis_id, turn_id=turn_id, msg=tm)
        bus.publish(
            channel,
            AnalysisEvent(
                type="done",
                data={
                    "sequence_end": ai_row.sequence,
                    "model": analysis.llm_deep_model,
                    "cost_usd": None,
                },
            ),
        )

    except asyncio.CancelledError:
        _persist_assistant(
            db,
            analysis_id=analysis_id,
            turn_id=turn_id,
            content_blocks=_final_blocks(),
            tool_calls=None,
            model_id=None,
            cost_usd=None,
            partial=True,
            cancelled=True,
            error=None,
        )
        bus.publish(channel, AnalysisEvent(type="cancelled", data={}))
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat turn %s failed", turn_id)
        _persist_assistant(
            db,
            analysis_id=analysis_id,
            turn_id=turn_id,
            content_blocks=_final_blocks(),
            tool_calls=None,
            model_id=None,
            cost_usd=None,
            partial=True,
            cancelled=False,
            error=str(exc)[:2000],
        )
        bus.publish(channel, AnalysisEvent(type="error", data={"message": str(exc)}))
    finally:
        bus.publish(channel, AnalysisEvent(type="close", data={}))
        bus.finish(channel)
        _RUNNING_TURNS.pop(turn_id, None)
        db.close()
