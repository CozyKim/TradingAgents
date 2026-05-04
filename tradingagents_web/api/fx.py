"""Read-only API for FX (foreign exchange) rates."""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends

from tradingagents_web.auth import get_current_user
from tradingagents_web.models import User
from tradingagents_web.schemas.fx import FxRate
from tradingagents_web.services import fx as fx_svc

router = APIRouter(prefix="/api/fx", tags=["fx"])


@router.get("/usd-krw", response_model=FxRate)
async def usd_krw(
    _user: Annotated[User, Depends(get_current_user)],
) -> FxRate:
    return await asyncio.to_thread(fx_svc.get_usd_krw_rate)
