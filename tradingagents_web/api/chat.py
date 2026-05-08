"""Chat API: 분석별 후속 대화."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as OrmSession
from sse_starlette.sse import EventSourceResponse

from tradingagents_web.auth import get_current_user, require_xhr
from tradingagents_web.db import get_db
from tradingagents_web.models import Analysis, ChatMessage, User
from tradingagents_web.schemas.chat import (
    ChatMessageListResponse,
    ChatMessageOut,
    ChatTurnCreateRequest,
    ChatTurnCreateResponse,
)
from tradingagents_web.services.chat_runner import (
    _RUNNING_TURNS,
    _execute_turn,
    chat_channel,
)
from tradingagents_web.services.event_bus import get_event_bus

router = APIRouter(prefix="/api/runs/{run_id}/chat", tags=["chat"])


def _get_completed_analysis(db: OrmSession, run_id: str) -> Analysis:
    a = db.query(Analysis).filter_by(run_id=run_id).first()
    if a is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if a.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot chat on a run in status '{a.status}'",
        )
    return a


def _has_inflight_turn(db: OrmSession, analysis_id: int) -> bool:
    """현재 분석에 진행 중인 turn이 있는지 확인."""
    if not _RUNNING_TURNS:
        return False
    running_turns = list(_RUNNING_TURNS.keys())
    owned = (
        db.query(ChatMessage.turn_id)
        .filter(
            ChatMessage.analysis_id == analysis_id,
            ChatMessage.turn_id.in_(running_turns),
        )
        .first()
    )
    return owned is not None


def _spawn_turn_task(*, run_id: str, analysis_id: int, turn_id: str) -> None:
    """백그라운드 task 생성 + _RUNNING_TURNS 등록."""
    task = asyncio.create_task(
        _execute_turn(run_id=run_id, analysis_id=analysis_id, turn_id=turn_id)
    )
    _RUNNING_TURNS[turn_id] = task
    task.add_done_callback(lambda _t: _RUNNING_TURNS.pop(turn_id, None))


@router.post(
    "/turns",
    response_model=ChatTurnCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_turn(
    run_id: str,
    payload: ChatTurnCreateRequest,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> ChatTurnCreateResponse:
    """사용자 메시지를 영속화하고 어시스턴트 응답 백그라운드 task를 시작한다."""
    a = _get_completed_analysis(db, run_id)
    if _has_inflight_turn(db, a.id):
        raise HTTPException(
            status_code=409,
            detail="Another turn is already in progress",
        )

    turn_id = str(uuid.uuid4())
    last = (
        db.query(ChatMessage.sequence)
        .filter_by(analysis_id=a.id)
        .order_by(ChatMessage.sequence.desc())
        .first()
    )
    seq = (last[0] + 1) if last else 0
    db.add(
        ChatMessage(
            analysis_id=a.id,
            turn_id=turn_id,
            sequence=seq,
            role="user",
            content_blocks=[{"type": "text", "text": payload.text}],
            completed_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    _spawn_turn_task(run_id=run_id, analysis_id=a.id, turn_id=turn_id)
    return ChatTurnCreateResponse(turn_id=turn_id)


@router.get("/messages", response_model=ChatMessageListResponse)
def list_messages(
    run_id: str,
    db: Annotated[OrmSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> ChatMessageListResponse:
    """분석에 속한 모든 채팅 메시지를 시간순으로 반환."""
    a = db.query(Analysis).filter_by(run_id=run_id).first()
    if a is None:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = (
        db.query(ChatMessage)
        .filter_by(analysis_id=a.id)
        .order_by(ChatMessage.sequence.asc())
        .all()
    )
    return ChatMessageListResponse(
        items=[ChatMessageOut.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.get("/turns/{turn_id}/stream")
async def stream_turn(
    run_id: str,
    turn_id: str,
    _user: Annotated[User, Depends(get_current_user)],
) -> EventSourceResponse:
    """SSE: turn의 token/tool_call/tool_result/done/error/cancelled/close 이벤트 스트림."""
    bus = get_event_bus()
    channel = chat_channel(run_id, turn_id)

    async def gen():
        async with bus.subscribe(channel) as queue:
            while True:
                ev = await queue.get()
                if ev is None:
                    return
                yield {
                    "event": ev.type,
                    "id": str(ev.seq),
                    "data": json.dumps(ev.data, default=str),
                }

    return EventSourceResponse(
        gen(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/turns/{turn_id}")
def cancel_turn(
    run_id: str,
    turn_id: str,
    _user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_xhr)] = None,
) -> dict[str, bool]:
    """진행 중 turn을 취소(asyncio.Task.cancel)한다."""
    task = _RUNNING_TURNS.get(turn_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Turn not in progress")
    task.cancel()
    return {"ok": True}
