"""Read-only API for ticker price history."""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from tradingagents_web.auth import get_current_user
from tradingagents_web.models import User
from tradingagents_web.schemas.price import PriceHistoryResponse
from tradingagents_web.services import prices as prices_svc

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("/{ticker}/history", response_model=PriceHistoryResponse)
async def history(
    ticker: str,
    _user: Annotated[User, Depends(get_current_user)],
    days: int = Query(default=90, ge=1, le=730),
) -> PriceHistoryResponse:
    return await asyncio.to_thread(prices_svc.get_price_history, ticker, days)
