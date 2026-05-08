"""Chat API request/response schemas."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageOut(BaseModel):
    """ChatMessage ORM의 외부 응답 표현."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    turn_id: str
    sequence: int
    role: Literal["user", "assistant", "tool"]
    content_blocks: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    partial: bool
    cancelled: bool
    error: str | None = None
    cost_usd: float | None = None
    model_id: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ChatMessageListResponse(BaseModel):
    """페이지네이션 없는 메시지 목록 응답."""

    items: list[ChatMessageOut]
    total: int


class ChatTurnCreateRequest(BaseModel):
    """사용자 메시지 입력."""

    text: str = Field(min_length=1, max_length=8000)


class ChatTurnCreateResponse(BaseModel):
    """turn 생성 응답."""

    turn_id: str
