"""Pydantic schemas for the alerts API."""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AlertType(str, Enum):
    SIGNAL_CHANGE = "signal_change"
    CONFIDENCE_CHANGE = "confidence_change"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    SCHEDULE_FAILED = "schedule_failed"


class AlertItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: AlertType
    ticker: str | None
    analysis_id: int | None
    schedule_id: int | None
    payload: dict[str, Any]
    read: bool
    created_at: datetime


class AlertListResponse(BaseModel):
    items: list[AlertItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class UnreadCountResponse(BaseModel):
    unread: int = Field(ge=0)
