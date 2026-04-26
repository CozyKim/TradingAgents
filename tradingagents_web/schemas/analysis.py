"""Pydantic schemas for the analyses API."""
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


VALID_ANALYSTS = {"market", "social", "news", "fundamentals"}


class Status(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Decision(str, Enum):
    BUY = "BUY"
    OVERWEIGHT = "OVERWEIGHT"
    HOLD = "HOLD"
    UNDERWEIGHT = "UNDERWEIGHT"
    SELL = "SELL"


class AnalysisCreateRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    analysis_date: date
    analysts: list[str] = Field(
        default_factory=lambda: ["market", "social", "news", "fundamentals"]
    )
    debate_rounds: int = Field(default=1, ge=1, le=5)
    llm_provider: str | None = None
    llm_deep_model: str | None = None
    llm_quick_model: str | None = None

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be blank")
        return v

    @field_validator("analysts")
    @classmethod
    def _validate_analysts(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("at least one analyst required")
        bad = [a for a in v if a not in VALID_ANALYSTS]
        if bad:
            raise ValueError(f"unknown analysts: {bad}")
        return v


class AnalysisListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    ticker: str
    analysis_date: date
    status: Status
    decision: Decision | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    created_at: datetime | str
    completed_at: datetime | None = None
    schedule_id: int | None = None


class AnalysisDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    ticker: str
    analysis_date: date
    status: Status
    decision: Decision | None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    llm_provider: str
    llm_deep_model: str
    llm_quick_model: str
    debate_rounds: int
    analysts: list[str]
    final_state: dict[str, Any] | None
    error: str | None
    cost_usd: float | None
    created_at: datetime
    completed_at: datetime | None
    schedule_id: int | None = None


class AnalysisCreateResponse(BaseModel):
    run_id: str


class AnalysisListResponse(BaseModel):
    items: list[AnalysisListItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
