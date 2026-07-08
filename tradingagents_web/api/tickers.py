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
    tickers: str = "",
) -> TickerNamesResponse:
    """쉼표로 구분된 티커들을 표시명(한글 우선)으로 해석한다.

    정규화(공백 제거·대문자화)와 중복 제거를 개수 상한 계산 **전에** 수행한다.
    그래서 동일 티커를 아무리 많이 보내도 dedupe 후 개수가 상한 이하면 통과한다.

    길이 상한은 ``tickers.split(",")`` 로 나누기 **전**, raw 쿼리 문자열에 대해
    검사한다 — 그래야 초장문 쿼리로 거대한 리스트를 만들어 dedupe/개수 검사에
    부담을 주는 경로 자체를 차단한다. ``Query(max_length=...)`` 제약은 쓰지 않는다.
    FastAPI 자체 검증은 길이 초과 시 ``detail`` 을 ``list[dict]`` 로 내는데, 이는
    개수 초과 시 우리가 내는 문자열 ``detail`` 과 스키마가 달라 호출부가 같은 422를
    두 가지 형태로 파싱해야 하는 문제를 낳는다. 두 검사 모두 여기서 문자열
    ``detail`` 로 통일한다.

    해석에 실패한 티커는 응답에서 생략된다. 호출부는 키 부재를 "이름 없음"으로 읽는다.

    Args:
        _user: 인증된 사용자 (세션 쿠키로 해석되며 값 자체는 쓰지 않는다).
        db: 동기 SQLAlchemy 세션. 표시명 3계층 캐시(DB→negative 캐시→업스트림) 조회에 쓰인다.
        tickers: 쉼표로 구분된 원본 티커 문자열. 대소문자·공백·중복은 이 라우트가 정리한다.

    Returns:
        {대문자 티커: 표시명} 매핑. 해석에 실패한 티커는 키 자체가 없다.

    Raises:
        HTTPException: 쿼리 문자열 길이가 ``_MAX_TICKERS_LEN`` 자를 넘거나, 정규화·
            중복 제거 후 티커 개수가 ``_MAX_TICKERS`` 개를 넘으면 422로 거절한다.
            두 경우 모두 ``detail`` 은 문자열이다.
    """
    if len(tickers) > _MAX_TICKERS_LEN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"티커 목록 문자열이 너무 깁니다 (최대 {_MAX_TICKERS_LEN}자).",
        )
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
