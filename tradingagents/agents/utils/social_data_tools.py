"""LangChain tool wrappers for the social_data category."""

from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_social_sentiment(
    ticker: Annotated[str, "Ticker symbol, e.g. AAPL"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Aggregated social sentiment metrics for a ticker.

    Returns a markdown report containing daily Reddit and Twitter mention
    counts plus bullish/bearish score breakdowns within [start_date, end_date].
    """
    return route_to_vendor("get_social_sentiment", ticker, start_date, end_date)


@tool
def get_social_messages(
    ticker: Annotated[str, "Ticker symbol, e.g. AAPL"],
    limit: Annotated[int, "Maximum messages to return (default 30, max 50)"] = 30,
) -> str:
    """Recent retail-investor messages for a ticker (StockTwits public stream).

    Returns a markdown list of recent messages with body, created_at, and an
    explicit Bullish/Bearish/None sentiment label per message.
    """
    return route_to_vendor("get_social_messages", ticker, limit)
