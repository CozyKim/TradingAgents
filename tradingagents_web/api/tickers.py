"""Read-only API for real-time ticker search (US + KR, stocks & ETFs)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from tradingagents_web.auth import get_current_user
from tradingagents_web.models import User
from tradingagents_web.schemas.ticker_search import TickerSearchResponse
from tradingagents_web.services import ticker_search as ticker_search_svc

router = APIRouter(prefix="/api/tickers", tags=["tickers"])


@router.get("/search", response_model=TickerSearchResponse)
async def search(
    _user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(max_length=64)] = "",
) -> TickerSearchResponse:
    """티커/회사명(영문·한글)으로 US·KR 주식·ETF를 검색한다."""
    results = await ticker_search_svc.search_tickers(q)
    return TickerSearchResponse(results=results)
