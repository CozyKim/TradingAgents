"""Hot-sector (trending) discovery service.

Pipeline: discover (recency-filtered KR+EN web search -> LLM theme extraction)
-> enrich (StockTwits + price momentum per theme ticker) -> score -> rank.

External dependencies (web search, social, price) are injected as callables
so the pipeline is deterministic under test. Network/LLM failures degrade to
empty/zeroed signals rather than raising — a trending scan must never crash.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

# Number of recency-filtered web searches per scan (natural budget cap —
# there is no ReAct loop here, just a fixed seed-query set).
_MAX_SEARCHES = 6
# Tavily recency window (days) for trending discovery.
_SEARCH_DAYS = 14

_EN_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def build_seed_queries(today: date) -> list[str]:
    """Build KR + EN seed queries anchored to the current year/month.

    Args:
        today: The scan's anchor date (injected for deterministic tests).

    Returns:
        A list of search query strings mixing Korean and English so both
        Korean and US trending themes surface.
    """
    y = today.year
    m_kr = f"{today.month}월"
    m_en = f"{_EN_MONTHS[today.month - 1]} {y}"
    return [
        f"{y}년 {m_kr} 지금 뜨는 투자 테마 주식",
        f"{y}년 {m_kr} 급등 섹터 종목",
        f"{y}년 {m_kr} 이번 주 화제의 종목 커뮤니티",
        f"trending stock themes {m_en}",
        f"hottest market sectors {m_en} retail investors",
        f"stocks reddit wallstreetbets trending {m_en}",
    ]


def search_recent(
    query: str,
    *,
    days: int,
    client_search: Callable[..., dict] | None = None,
) -> list[dict[str, Any]]:
    """Run one recency-filtered Tavily search; never raises.

    Args:
        query: The search query.
        days: Recency window passed to Tavily (topic="news").
        client_search: Injectable Tavily ``client.search`` (tests pass a fake).
            When None, a real TavilyClient is constructed from TAVILY_API_KEY.

    Returns:
        List of {title, url, snippet, published_date}. Empty on any failure
        or missing API key.
    """
    try:
        if client_search is None:
            api_key = os.environ.get("TAVILY_API_KEY")
            if not api_key:
                logger.warning("TAVILY_API_KEY not set; search_recent returning []")
                return []
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            client_search = client.search
        raw = client_search(
            query,
            max_results=5,
            search_depth="advanced",
            topic="news",
            days=days,
        )
    except Exception:  # noqa: BLE001 — search must never crash a scan
        logger.exception("trending search_recent failed for %r", query)
        return []

    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
            "published_date": r.get("published_date", ""),
        }
        for r in raw.get("results", [])
    ]
