"""Finnhub company-news vendor used as a sentiment-signal source.

Note on the endpoint choice: Finnhub's ``/stock/social-sentiment`` and
``/news-sentiment`` are now premium-only (HTTP 403 on the free tier as of
2026-05-08). ``/company-news`` is free, returns hundreds of recent headlines
+ summaries, and lets the analyst LLM aggregate sentiment itself. We keep
the public function name (``get_social_sentiment_finnhub``) and tool name
(``get_social_sentiment``) so the routing wiring stays put — only the
underlying data source changed.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import requests

from .finnhub_common import finnhub_get, get_api_key

_log = logging.getLogger(__name__)

_DEFAULT_MAX_ITEMS = 20
_SUMMARY_MAX = 240


def _format_unix_date(ts: Any) -> str:
    """Convert a unix timestamp (int/float) to yyyy-mm-dd; fall back to '(unknown)'."""
    try:
        if not ts:
            return "(unknown)"
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return "(unknown)"


def _truncate_summary(text: str) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= _SUMMARY_MAX else text[: _SUMMARY_MAX - 1] + "…"


def get_social_sentiment_finnhub(
    ticker: str,
    start_date: str,
    end_date: str,
    max_items: int = _DEFAULT_MAX_ITEMS,
) -> str:
    """Fetch Finnhub ``/company-news`` and render a daily-grouped markdown digest.

    Returns the most recent ``max_items`` headlines (newest first) grouped by
    publication date. The analyst LLM uses this as the primary input for
    deriving sentiment direction and notable narratives — the actual social
    sentiment endpoint is no longer accessible on the free Finnhub tier.

    Args:
        ticker: Bare ticker symbol (e.g. "AAPL").
        start_date: yyyy-mm-dd inclusive.
        end_date: yyyy-mm-dd inclusive.
        max_items: Maximum headlines to render (default 20). Clamped to [1, 50].

    Returns:
        A markdown string. On missing key or network error, returns a user-visible
        explanation string (not an exception). On 401/403/429, raises so
        ``route_to_vendor`` can fall through.
    """
    if not get_api_key():
        return (
            "FINNHUB_API_KEY not set; company-news signal unavailable. "
            "Set FINNHUB_API_KEY to enable."
        )

    try:
        body = finnhub_get(
            "/company-news",
            {"symbol": ticker, "from": start_date, "to": end_date},
        )
    except requests.RequestException as exc:
        _log.warning("finnhub company-news network error: %s", exc)
        return f"Error fetching company news for {ticker}: {exc}"

    # finnhub_get wraps list payloads under "items".
    items: list[dict[str, Any]] = body.get("items") or []
    if not items:
        return (
            f"No company news for {ticker} between {start_date} and {end_date}."
        )

    capped = max(1, min(int(max_items), 50))
    items_sorted = sorted(items, key=lambda it: it.get("datetime", 0), reverse=True)[:capped]

    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in items_sorted:
        by_day[_format_unix_date(it.get("datetime"))].append(it)

    parts = [
        f"## Company News & Sentiment Signals — {ticker} ({start_date} → {end_date})",
        "",
        f"_Source: Finnhub /company-news. Top {len(items_sorted)} of {len(items)} items, newest first._",
        "",
    ]
    for date in sorted(by_day.keys(), reverse=True):
        parts.append(f"### {date}")
        for it in by_day[date]:
            headline = it.get("headline") or "(no headline)"
            source = it.get("source") or "?"
            parts.append(f"- **{headline}** ({source})")
            summary = _truncate_summary(it.get("summary", ""))
            if summary:
                parts.append(f"  {summary}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"
