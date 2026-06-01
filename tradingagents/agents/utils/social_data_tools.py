"""LangChain tool wrappers for the social_data category."""

from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.dataflows.naver_finance_board import _extract_krx_code


@tool
def get_social_sentiment(
    ticker: Annotated[str, "Ticker symbol, e.g. AAPL"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """News-based sentiment signal for a ticker within [start_date, end_date].

    Backed by Finnhub company-news (US coverage). Korean tickers (.KS/.KQ) are
    not covered here — for Korean retail sentiment use get_social_messages, which
    reads the Naver 종목토론방.
    """
    if _extract_krx_code(ticker) is not None:
        return (
            f"{ticker} (Korean) has no news-sentiment source here; "
            "call get_social_messages for Naver 종목토론방 retail posts instead."
        )
    return route_to_vendor("get_social_sentiment", ticker, start_date, end_date)


@tool
def get_social_messages(
    ticker: Annotated[str, "Ticker symbol, e.g. AAPL or 005930.KS for Korean stocks"],
    limit: Annotated[int, "Maximum messages to return (default 30, max 50)"] = 30,
    sort: Annotated[
        str | None,
        "'latest' (newest first) or 'views' (most-viewed first). Default: Korean "
        ".KS/.KQ tickers → 'views', US tickers → 'latest'.",
    ] = None,
    days: Annotated[
        int | None,
        "Korean tickers only: keep only posts from the last N days. Defaults to 3 "
        "for Korean tickers (지난 3일), None (no window) for US tickers.",
    ] = None,
) -> str:
    """Recent retail-investor messages for a ticker.

    US tickers use the StockTwits public stream (each message tagged
    Bullish/Bearish/None, always newest-first). Korean tickers (.KS/.KQ) use the
    Naver 종목토론방 retail board (each post shows view + 추천 counts) and default
    to the most-viewed posts of the last 3 days (지난 3일 조회순); pass an explicit
    ``sort``/``days`` to override. StockTwits ignores ``sort``/``days``.
    """
    is_korean = _extract_krx_code(ticker) is not None
    if sort is None:
        sort = "views" if is_korean else "latest"
    if is_korean and days is None:
        days = 3
    return route_to_vendor("get_social_messages", ticker, limit, sort=sort, days=days)
