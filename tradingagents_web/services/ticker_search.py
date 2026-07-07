"""Real-time ticker search: routes queries to Naver (한글) or Yahoo (영문/티커),
normalizes hits to US/KR stocks & ETFs. Uses httpx (not yfinance)."""

from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from typing import Literal

import httpx

from tradingagents_web.schemas.ticker_search import TickerSearchResult

# 야후 스타일 비(非)미국 거래소 접미사. web/lib/ticker-market.ts 와 동일 목록.
_GLOBAL_SUFFIXES: tuple[str, ...] = (
    ".T",
    ".HK",
    ".L",
    ".DE",
    ".PA",
    ".SS",
    ".SZ",
    ".TO",
    ".AX",
    ".SW",
    ".MI",
    ".HE",
    ".ST",
    ".AS",
    ".BR",
    ".MC",
    ".SI",
    ".TW",
    ".NS",
    ".BO",
    ".F",
    ".VI",
    ".LS",
    ".OL",
    ".CO",
    ".KL",
    ".JK",
    ".SA",
    ".MX",
    ".BA",
    ".SN",
)
_YAHOO_TYPES: frozenset[str] = frozenset({"EQUITY", "ETF"})
_NAVER_KR_SUFFIX: dict[str, str] = {"KOSPI": ".KS", "KOSDAQ": ".KQ"}
# 주식+ETF 목적에 맞춰 제외할 파생/구조화 상품 이름 패턴.
_NAVER_DERIV_PATTERNS: tuple[str, ...] = ("레버리지", "인버스", "선물", "채권혼합", "2X", "3X")
# 레버리지/인버스/파생 상품 이름 패턴(대문자 비교). 스펙: 주식+ETF만, 노이즈 제거.
_YAHOO_DERIV_PATTERNS: tuple[str, ...] = ("2X", "3X", "-1X", "LEVERAGED", "INVERSE", "DAILY TARGET", "DRN", "ETN")


def _classify_market(symbol: str) -> Literal["US", "KR"] | None:
    """티커 접미사로 상장 시장을 판별한다.

    Args:
        symbol: 야후/네이버 정규화 후의 티커 문자열.

    Returns:
        "KR" 또는 "US". 글로벌 접미사이거나 빈 문자열이면 None(결과에서 제외).
    """
    s = symbol.strip().upper()
    if not s:
        return None
    if s.endswith(".KS") or s.endswith(".KQ"):
        return "KR"
    if any(s.endswith(suffix) for suffix in _GLOBAL_SUFFIXES):
        return None
    return "US"


def _normalize_yahoo_quote(quote: object) -> TickerSearchResult | None:
    """Yahoo search quote 항목을 정규화한다(EQUITY/ETF·US/KR만 통과)."""
    if not isinstance(quote, dict):
        return None
    if quote.get("quoteType") not in _YAHOO_TYPES:
        return None
    symbol = quote.get("symbol") or ""
    market = _classify_market(symbol)
    if market is None:
        return None
    name = quote.get("shortname") or quote.get("longname") or symbol
    if any(pattern in name.upper() for pattern in _YAHOO_DERIV_PATTERNS):
        return None
    return TickerSearchResult(ticker=symbol, name=name, market=market, exchange=quote.get("exchange"))


def _normalize_naver_item(item: object) -> TickerSearchResult | None:
    """Naver 자동완성 item 을 정규화한다(KOR KOSPI/KOSDAQ 또는 USA만 통과)."""
    if not isinstance(item, dict):
        return None
    name = item.get("name") or ""
    if any(pattern in name for pattern in _NAVER_DERIV_PATTERNS):
        return None
    code = item.get("code") or ""
    nation = item.get("nationCode")
    if nation == "KOR":
        suffix = _NAVER_KR_SUFFIX.get(item.get("typeCode") or "")
        if suffix is None:
            return None
        return TickerSearchResult(ticker=f"{code}{suffix}", name=name, market="KR", exchange=item.get("typeCode"))
    if nation == "USA":
        return TickerSearchResult(ticker=code, name=name, market="US", exchange=item.get("typeCode"))
    return None


_CACHE: "OrderedDict[str, tuple[float, list[TickerSearchResult]]]" = OrderedDict()
_CACHE_TTL: float = 300.0  # 5분
_CACHE_MAX: int = 512


def _now() -> float:
    """단조 시각(초). 테스트에서 monkeypatch 하기 위한 간접 계층."""
    return time.monotonic()


def _cache_key(query: str) -> str:
    return query.strip().lower()


def _cache_get(query: str) -> list[TickerSearchResult] | None:
    """캐시 조회. 만료 항목은 폐기하고 None 반환. 히트 시 LRU 갱신."""
    key = _cache_key(query)
    hit = _CACHE.get(key)
    if hit is None:
        return None
    stamped_at, value = hit
    if _now() - stamped_at > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    _CACHE.move_to_end(key)
    return value


def _cache_put(query: str, results: list[TickerSearchResult]) -> None:
    """캐시에 저장하고 상한 초과 시 LRU 축출."""
    key = _cache_key(query)
    _CACHE[key] = (_now(), results)
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)


logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0, connect=5.0)
_USER_AGENT = "Mozilla/5.0 (compatible; TradingAgents/1.0)"
_MAX_QUERY_LEN = 64
_MAX_RESULTS = 10
# 한글 자모(호환) + 완성형 음절. web/lib/ticker-search.ts 의 HANGUL_RE 와 정합.
_HANGUL_RE = re.compile(r"[ㄱ-ㆎ가-힣]")


def _has_hangul(text: str) -> bool:
    """문자열에 한글이 포함되면 True."""
    return bool(_HANGUL_RE.search(text))


async def _search_yahoo(query: str) -> list[TickerSearchResult]:
    """Yahoo Finance search 엔드포인트로 영문/티커 질의를 조회한다."""
    url = "https://query1.finance.yahoo.com/v1/finance/search"
    params = {"q": query, "quotesCount": _MAX_RESULTS, "newsCount": 0}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params, headers={"User-Agent": _USER_AGENT})
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        return []
    out: list[TickerSearchResult] = []
    for quote in data.get("quotes", []):
        result = _normalize_yahoo_quote(quote)
        if result is not None:
            out.append(result)
    return out[:_MAX_RESULTS]


async def _search_naver(query: str) -> list[TickerSearchResult]:
    """Naver 자동완성으로 한글명 질의(KRX + 미국 인기주)를 조회한다."""
    url = "https://ac.stock.naver.com/ac"
    params = {"q": query, "target": "stock", "st": 1}
    headers = {"User-Agent": _USER_AGENT, "Referer": "https://finance.naver.com/"}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        return []
    out: list[TickerSearchResult] = []
    for item in data.get("items", []):
        result = _normalize_naver_item(item)
        if result is not None:
            out.append(result)
    return out[:_MAX_RESULTS]


async def search_tickers(query: str) -> list[TickerSearchResult]:
    """질의를 소스로 라우팅해 정규화된 결과를 반환한다.

    한글 포함 질의는 Naver, 그 외는 Yahoo로 라우팅한다. 캐시 히트 시 업스트림을
    호출하지 않으며, 업스트림 실패/타임아웃 시 빈 리스트를 반환한다(검색은 부가기능).

    Args:
        query: 사용자 입력 문자열.

    Returns:
        최대 10개의 정규화된 TickerSearchResult. 빈 질의/실패 시 빈 리스트.
    """
    q = query.strip()[:_MAX_QUERY_LEN]
    if not q:
        return []
    cached = _cache_get(q)
    if cached is not None:
        return cached
    try:
        results = await _search_naver(q) if _has_hangul(q) else await _search_yahoo(q)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("ticker search upstream failed for %r: %s", q, exc)
        return []
    _cache_put(q, results)
    return results
