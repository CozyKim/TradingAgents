"""Pydantic schemas for the schedules API."""
from datetime import datetime
from typing import Literal

from croniter import croniter
from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_ANALYSTS = {"market", "social", "news", "fundamentals"}


class SchedulePreset(BaseModel):
    analysts: list[str] = Field(..., min_length=1)
    debate_rounds: int = Field(default=1, ge=1, le=5)
    llm_provider: str | None = None
    llm_deep_model: str | None = None
    llm_quick_model: str | None = None

    @field_validator("analysts")
    @classmethod
    def _check_analysts(cls, v: list[str]) -> list[str]:
        bad = [a for a in v if a not in VALID_ANALYSTS]
        if bad:
            raise ValueError(f"unknown analysts: {bad}")
        return v


def _validate_cron(value: str) -> str:
    value = value.strip()
    if not croniter.is_valid(value):
        raise ValueError(f"invalid cron expression: {value!r}")
    return value


class ScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    ticker: str = Field(..., min_length=1, max_length=16)
    cron_expr: str
    preset: SchedulePreset
    active: bool = True

    @field_validator("ticker")
    @classmethod
    def _norm_ticker(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be blank")
        return v

    @field_validator("cron_expr")
    @classmethod
    def _check_cron(cls, v: str) -> str:
        return _validate_cron(v)


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    cron_expr: str | None = None
    preset: SchedulePreset | None = None
    active: bool | None = None

    @field_validator("cron_expr")
    @classmethod
    def _check_cron(cls, v: str | None) -> str | None:
        return _validate_cron(v) if v is not None else None


class ScheduleItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ticker: str
    cron_expr: str
    preset: dict
    active: bool
    last_run: datetime | None
    next_run: datetime | None
    source: Literal["user", "holding"]
    holding_id: int | None
    created_at: datetime


class ScheduleListResponse(BaseModel):
    items: list[ScheduleItem]
