"""Real-time ticker search: routes queries to Naver (한글) or Yahoo (영문/티커),
normalizes hits to US/KR stocks & ETFs. Uses httpx (not yfinance)."""
from __future__ import annotations

from tradingagents_web.schemas.ticker_search import TickerSearchResult

# 야후 스타일 비(非)미국 거래소 접미사. web/lib/ticker-market.ts 와 동일 목록.
_GLOBAL_SUFFIXES: tuple[str, ...] = (
    ".T", ".HK", ".L", ".DE", ".PA", ".SS", ".SZ", ".TO", ".AX",
    ".SW", ".MI", ".HE", ".ST", ".AS", ".BR", ".MC", ".SI", ".TW",
    ".NS", ".BO", ".F", ".VI", ".LS", ".OL", ".CO", ".KL", ".JK",
)
_YAHOO_TYPES: frozenset[str] = frozenset({"EQUITY", "ETF"})
_NAVER_KR_SUFFIX: dict[str, str] = {"KOSPI": ".KS", "KOSDAQ": ".KQ"}
# 주식+ETF 목적에 맞춰 제외할 파생/구조화 상품 이름 패턴.
_NAVER_DERIV_PATTERNS: tuple[str, ...] = ("레버리지", "인버스", "선물", "채권혼합", "2X", "3X")


def _classify_market(symbol: str) -> str | None:
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


def _normalize_yahoo_quote(quote: dict) -> TickerSearchResult | None:
    """Yahoo search quote 항목을 정규화한다(EQUITY/ETF·US/KR만 통과)."""
    if quote.get("quoteType") not in _YAHOO_TYPES:
        return None
    symbol = quote.get("symbol") or ""
    market = _classify_market(symbol)
    if market is None:
        return None
    name = quote.get("shortname") or quote.get("longname") or symbol
    return TickerSearchResult(ticker=symbol, name=name, market=market, exchange=quote.get("exchange"))


def _normalize_naver_item(item: dict) -> TickerSearchResult | None:
    """Naver 자동완성 item 을 정규화한다(KOR KOSPI/KOSDAQ 또는 USA만 통과)."""
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
