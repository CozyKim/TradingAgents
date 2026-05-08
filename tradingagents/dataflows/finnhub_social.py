"""Finnhub social sentiment vendor."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import requests

from .finnhub_common import finnhub_get, get_api_key

_log = logging.getLogger(__name__)


def _aggregate_by_day(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse intraday entries to daily rows.

    `mentions` is summed across all intraday buckets for the day.
    `positive` / `negative` are *averaged* across buckets (they are scores in
    [0, 1], not counts), and `net = positive - negative`.
    """
    by_day: dict[str, dict] = defaultdict(lambda: {"mentions": 0, "pos": 0.0, "neg": 0.0, "n": 0})
    for entry in entries:
        at = str(entry.get("atTime") or entry.get("date") or "")[:10]
        if not at:
            continue
        bucket = by_day[at]
        bucket["mentions"] += int(entry.get("mention", 0) or 0)
        bucket["pos"] += float(entry.get("positiveScore", 0) or 0)
        bucket["neg"] += float(entry.get("negativeScore", 0) or 0)
        bucket["n"] += 1
    out = []
    for date, b in sorted(by_day.items()):
        n = max(b["n"], 1)
        out.append({
            "date": date,
            "mentions": b["mentions"],
            "positive": round(b["pos"] / n, 3),
            "negative": round(b["neg"] / n, 3),
            "net": round((b["pos"] - b["neg"]) / n, 3),
        })
    return out


def _render_table(title: str, rows: list[dict[str, Any]]) -> str:
    """Render a daily-aggregated rows list as a markdown table under ``title``."""
    if not rows:
        return f"#### {title}\n\n_No data._\n"
    out = [f"#### {title}", "", "| date | mentions | positive | negative | net |",
           "|---|---:|---:|---:|---:|"]
    for r in rows:
        out.append(f"| {r['date']} | {r['mentions']} | {r['positive']} | {r['negative']} | {r['net']} |")
    out.append("")
    return "\n".join(out)


def get_social_sentiment_finnhub(ticker: str, start_date: str, end_date: str) -> str:
    """Fetch Finnhub /stock/social-sentiment and render a markdown report.

    Args:
        ticker: Bare ticker symbol (e.g. "AAPL").
        start_date: yyyy-mm-dd inclusive.
        end_date: yyyy-mm-dd inclusive.

    Returns:
        A markdown string. On missing key or network error, returns a user-visible
        explanation string (not an exception). On 401/403/429, raises so
        route_to_vendor can fall through.
    """
    if not get_api_key():
        return "FINNHUB_API_KEY not set; social sentiment unavailable. Set FINNHUB_API_KEY to enable."

    try:
        body = finnhub_get(
            "/stock/social-sentiment",
            {"symbol": ticker, "from": start_date, "to": end_date},
        )
    except requests.RequestException as exc:
        _log.warning("finnhub social network error: %s", exc)
        return f"Error fetching social sentiment for {ticker}: {exc}"

    reddit = body.get("reddit") or []
    twitter = body.get("twitter") or []
    if not reddit and not twitter:
        return f"No social sentiment data for {ticker} between {start_date} and {end_date}."

    parts = [
        f"## Social Sentiment — {ticker} ({start_date} → {end_date})",
        "",
        _render_table("Reddit", _aggregate_by_day(reddit)),
        _render_table("Twitter", _aggregate_by_day(twitter)),
    ]
    return "\n".join(parts)
