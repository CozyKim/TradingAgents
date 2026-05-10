"""Pydantic schemas for the prices API."""
from datetime import date

from pydantic import BaseModel


class PricePoint(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceHistoryResponse(BaseModel):
    ticker: str
    points: list[PricePoint]
    last_close: float | None
