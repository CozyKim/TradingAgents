"""Ticker → display-name resolver (한글 우선).

검색(ticker_search)과 분리한 이유: 검색은 "질의어 → 후보 목록"이고 해석은
"티커 → 단일 이름"이다. 라우팅도 다르다 — 검색은 한글 포함 여부로 소스를 가르지만
해석은 한글명이 목적이므로 항상 Naver를 먼저 시도한다.

3계층 캐시: ticker_names 테이블(30일) → negative 캐시(5분) → 업스트림.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from tradingagents_web.models import TickerName
from tradingagents_web.models.base import utcnow
from tradingagents_web.schemas.ticker_search import TickerSearchResult
from tradingagents_web.services.ticker_search import _search_naver, _search_yahoo

logger = logging.getLogger(__name__)

_KR_SUFFIXES: tuple[str, ...] = (".KS", ".KQ")
_STALE_AFTER = timedelta(days=30)

# 해석 실패한 티커. DB에 쓰지 않는 대신 여기서 5분간 재질의를 막는다.
_MISS: "OrderedDict[str, float]" = OrderedDict()
_MISS_TTL: float = 300.0
_MISS_MAX: int = 512


def _now() -> float:
    """단조 시각(초). 테스트에서 monkeypatch 하기 위한 간접 계층."""
    return time.monotonic()


def _canonical(ticker: str) -> str:
    """티커를 Naver 질의어이자 비교 키인 표준형으로 바꾼다.

    실측 근거: ``005930.KS`` 는 매칭되지 않고 ``005930`` 은 삼성전자를 준다.
    ``BRK-B`` 도 매칭되지 않고 ``BRK.B`` 는 버크셔를 준다.

    두 역할을 겸한다 — Naver 에 보낼 질의어를 만들고, 응답 티커와 질의 티커를
    같은 기준으로 비교한다. 그래서 idempotent 여야 한다: _canonical(_canonical(x))
    == _canonical(x).

    Args:
        ticker: 원본 티커 (예: "005930.KS", "brk-b", "aapl").

    Returns:
        대문자 표준형.
    """
    s = ticker.strip().upper()
    for suffix in _KR_SUFFIXES:
        if s.endswith(suffix):
            # 한국 종목은 6자리 숫자 코드다. '-' 치환 대상이 아니다.
            return s[: -len(suffix)]
    return s.replace("-", ".")


def _pick_exact(results: list[TickerSearchResult], want: str) -> str | None:
    """정확히 일치하는 티커의 이름만 고른다.

    Naver 자동완성은 prefix 매칭이라 질의어와 무관한 종목이 1위로 올 수 있다
    (실측: q=GS → 1위가 한국 GS(078930), 2위가 골드만삭스). ``results[0]`` 를
    쓰면 엉뚱한 이름이 표시된다.

    ``want`` 와 응답 티커 **양쪽**에 _canonical 을 적용한다. 한쪽만 적용하면
    Yahoo 폴백에서 want="BRK-B", 응답="BRK-B" 인데 "BRK.B" != "BRK-B" 로
    조용히 None 이 된다.

    Args:
        results: 업스트림에서 정규화된 후보들.
        want: 질의 티커. 원본이든 _canonical 통과본이든 상관없다.

    Returns:
        일치하는 후보의 이름. 없으면 None.
    """
    target = _canonical(want)
    for result in results:
        if _canonical(result.ticker) == target:
            return result.name
    return None


def _miss_get(ticker: str) -> bool:
    """최근 해석에 실패한 티커면 True. 만료 항목은 폐기한다."""
    stamped_at = _MISS.get(ticker)
    if stamped_at is None:
        return False
    if _now() - stamped_at > _MISS_TTL:
        _MISS.pop(ticker, None)
        return False
    return True


def _miss_put(ticker: str) -> None:
    """해석 실패를 기록하고 상한 초과 시 LRU 축출한다."""
    _MISS[ticker] = _now()
    _MISS.move_to_end(ticker)
    while len(_MISS) > _MISS_MAX:
        _MISS.popitem(last=False)


def _is_fresh(row: TickerName) -> bool:
    """updated_at 이 30일 이내면 True.

    SQLite는 DateTime(timezone=True) 를 naive 로 돌려줄 수 있어 UTC로 보정한다.
    """
    stamped_at = row.updated_at
    if stamped_at.tzinfo is None:
        stamped_at = stamped_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - stamped_at < _STALE_AFTER


async def _resolve_one(ticker: str) -> str | None:
    """업스트림에서 티커 하나의 표시명을 얻는다. 실패하면 None.

    Naver 를 먼저 때린다 — 한글명이 목적이기 때문이다. Yahoo 는 Naver 가 모르는
    종목(지수, 일부 ETF)을 위한 영문명 안전망이다.

    Naver 와 Yahoo 를 별개의 try 로 감싼다. ``ac.stock.naver.com`` 은 스푸핑된
    UA/Referer 로 때리는 비공식 엔드포인트라 403/429/타임아웃이 현실적으로 자주
    난다. 두 업스트림을 하나의 try 로 묶으면 Naver 예외가 Yahoo 호출 자체를
    막아버려, Yahoo 가 멀쩡해도 모든 티커가 실패로 처리된다.

    Yahoo 에는 원본 티커를 그대로 보낸다. Yahoo 는 ``BRK-B``, ``005930.KS`` 표기를
    쓰므로 _canonical 을 적용하면 오히려 못 찾는다.

    ``TypeError``/``AttributeError`` 도 함께 잡는다. ``_normalize_yahoo_quote`` 는
    검증되지 않은 JSON 페이로드에 ``symbol.strip()``·``name.upper()`` 를 호출하므로
    이상한 응답이 오면 이 예외들이 튄다. 이름 표시는 부가 기능이라 실패해도 티커는
    보여야 한다 — 잡지 않으면 asyncio.gather 를 거쳐 같은 배치의 정상 티커까지
    통째로 버려지고 호출자가 500 을 받는다.
    """
    name: str | None = None
    try:
        naver_hits = await _search_naver(_canonical(ticker))
        name = _pick_exact(naver_hits, ticker)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        logger.warning("naver ticker name resolve failed for %r: %s", ticker, exc)
    if name is not None:
        return name

    try:
        yahoo_hits = await _search_yahoo(ticker)
        return _pick_exact(yahoo_hits, ticker)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        logger.warning("yahoo ticker name resolve failed for %r: %s", ticker, exc)
        return None


def _upsert(db: Session, ticker: str, name: str) -> None:
    """이름을 저장한다.

    updated_at 을 명시적으로 대입하는 이유: SQLAlchemy 의 onupdate 는 UPDATE 문이
    실제로 나갈 때만 작동한다. 재조회 결과가 이전과 같은 이름이면 ORM 이 UPDATE 를
    생략해 타임스탬프가 그대로 남고, 30일 경과 후 매 요청마다 업스트림을 때리게 된다.
    """
    row = db.get(TickerName, ticker)
    if row is None:
        db.add(TickerName(ticker=ticker, name=name))
    else:
        row.name = name
        row.updated_at = utcnow()
    db.commit()


async def resolve_names(tickers: Sequence[str], db: Session) -> dict[str, str]:
    """티커 목록을 표시명(한글 우선)으로 해석한다.

    DB 캐시 → negative 캐시 → 업스트림(Naver, 실패 시 Yahoo) 순으로 조회한다.
    해석에 실패한 티커는 **반환 딕셔너리에 키 자체가 없다**. 빈 문자열이나 티커
    자기 자신을 채우면 "이름 없음"과 "이름이 티커와 같음"을 구분할 수 없다.

    업스트림이 전면 장애여도 DB 에 있던 이름은 (만료됐더라도) 계속 서빙한다.

    Args:
        tickers: 원본 티커들. 대소문자·중복·공백은 이 함수가 정리한다.
        db: 동기 SQLAlchemy 세션.

    Returns:
        {대문자 티커: 표시명}. 해석 실패분은 생략된다.
    """
    wanted = list(dict.fromkeys(t.strip().upper() for t in tickers if t.strip()))
    if not wanted:
        return {}

    out: dict[str, str] = {}
    stale: dict[str, str] = {}  # 만료됐지만 업스트림 실패 시 되살릴 값
    todo: list[str] = []

    for ticker in wanted:
        row = db.get(TickerName, ticker)
        if row is not None and _is_fresh(row):
            out[ticker] = row.name
            continue
        if row is not None:
            stale[ticker] = row.name
        if not _miss_get(ticker):
            todo.append(ticker)
        elif ticker in stale:
            out[ticker] = stale[ticker]

    if not todo:
        return out

    resolved = await asyncio.gather(*(_resolve_one(t) for t in todo))
    for ticker, name in zip(todo, resolved, strict=True):
        if name is None:
            _miss_put(ticker)
            # 업스트림이 죽어도 예전 이름이 있으면 그걸 쓴다.
            if ticker in stale:
                out[ticker] = stale[ticker]
            continue
        _upsert(db, ticker, name)
        out[ticker] = name
    return out
