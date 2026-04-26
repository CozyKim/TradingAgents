"""Pydantic schemas for the holdings API."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HoldingCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=16)
    qty: float = Field(..., ge=0)
    avg_cost: float = Field(..., ge=0)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("ticker")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be blank")
        return v


class HoldingUpdate(BaseModel):
    qty: float | None = Field(default=None, ge=0)
    avg_cost: float | None = Field(default=None, ge=0)
    monitor_enabled: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class HoldingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    qty: float
    avg_cost: float
    monitor_enabled: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class HoldingListResponse(BaseModel):
    items: list[HoldingItem]
