"""Read-only API for real-time ticker search and name resolution (US + KR)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from tradingagents_web.auth import get_current_user
from tradingagents_web.db import get_db
from tradingagents_web.models import User
from tradingagents_web.schemas.ticker_search import TickerNamesResponse, TickerSearchResponse
from tradingagents_web.services import ticker_names as ticker_names_svc
from tradingagents_web.services import ticker_search as ticker_search_svc

router = APIRouter(prefix="/api/tickers", tags=["tickers"])

_MAX_TICKERS = 100
# 티커 16자 * 100 + 구분자 99 = 1699. 여유를 둔 상한.
_MAX_TICKERS_LEN = 2048


@router.get("/search", response_model=TickerSearchResponse)
async def search(
    _user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(max_length=64)] = "",
) -> TickerSearchResponse:
    """티커/회사명(영문·한글)으로 US·KR 주식·ETF를 검색한다."""
    results = await ticker_search_svc.search_tickers(q)
    return TickerSearchResponse(results=results)


@router.get("/names", response_model=TickerNamesResponse)
async def names(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    tickers: Annotated[str, Query(max_length=_MAX_TICKERS_LEN)] = "",
) -> TickerNamesResponse:
    """쉼표로 구분된 티커들을 표시명(한글 우선)으로 해석한다.

    해석에 실패한 티커는 응답에서 생략된다. 호출부는 키 부재를 "이름 없음"으로 읽는다.
    """
    wanted = list(dict.fromkeys(t.strip().upper() for t in tickers.split(",") if t.strip()))
    if not wanted:
        return TickerNamesResponse(names={})
    if len(wanted) > _MAX_TICKERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"최대 {_MAX_TICKERS}개의 티커만 한 번에 조회할 수 있습니다.",
        )
    resolved = await ticker_names_svc.resolve_names(wanted, db)
    return TickerNamesResponse(names=resolved)
