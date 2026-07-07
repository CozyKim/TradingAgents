"""Pydantic schemas for the ticker search API."""
from typing import Literal

from pydantic import BaseModel


class TickerSearchResult(BaseModel):
    """A single normalized ticker search hit (US or KR, stock or ETF)."""

    ticker: str            # 정규화된 최종 티커 (예: "AAPL", "005930.KS")
    name: str
    market: Literal["US", "KR"]
    exchange: str | None = None


class TickerSearchResponse(BaseModel):
    """Envelope for /api/tickers/search."""

    results: list[TickerSearchResult]
