"""Pydantic schemas for the prices API."""
from datetime import date

from pydantic import BaseModel


class PricePoint(BaseModel):
    date: date
    close: float


class PriceHistoryResponse(BaseModel):
    ticker: str
    points: list[PricePoint]
    last_close: float | None
