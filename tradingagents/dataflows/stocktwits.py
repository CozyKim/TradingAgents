"""StockTwits public stream vendor (no auth required)."""

from __future__ import annotations

import logging

import requests

API_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_TIMEOUT_SECONDS = 10
_BODY_MAX = 280
_log = logging.getLogger(__name__)


def _truncate(text: str, limit: int = _BODY_MAX) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def get_social_messages_stocktwits(ticker: str, limit: int = 30) -> str:
    """Fetch recent retail-investor messages for a ticker from StockTwits.

    Args:
        ticker: Bare ticker symbol (e.g. "AAPL").
        limit: Max messages, clamped to [1, 50].

    Returns:
        A markdown bullet list, or an explicit no-data message. Network-level
        errors are caught and surfaced as readable strings (not raised) — there
        is no fallback vendor for this method.
    """
    safe_limit = max(1, min(int(limit), 50))
    url = API_URL.format(ticker=ticker)

    try:
        resp = requests.get(url, params={"limit": safe_limit}, timeout=_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        _log.warning("stocktwits network error: %s", exc)
        return f"Error fetching StockTwits messages for {ticker}: {exc}"

    if resp.status_code == 404:
        return f"No StockTwits stream found for {ticker}."
    if resp.status_code == 429:
        return f"StockTwits rate-limited; try again later for {ticker}."

    try:
        resp.raise_for_status()
        body = resp.json()
    except (requests.RequestException, ValueError) as exc:
        return f"Error fetching StockTwits messages for {ticker}: {exc}"

    messages = body.get("messages") or []
    if not messages:
        return f"No StockTwits messages found for {ticker}."

    lines = [f"## StockTwits — {ticker} (last {len(messages)} messages)", ""]
    for m in messages:
        ts = m.get("created_at", "")
        user = (m.get("user") or {}).get("username", "?")
        sentiment_obj = (m.get("entities") or {}).get("sentiment") or {}
        sentiment = sentiment_obj.get("basic") if isinstance(sentiment_obj, dict) else None
        body_txt = _truncate(m.get("body", ""))
        lines.append(f"- [{ts}] ({sentiment}) @{user}: {body_txt}")
    return "\n".join(lines)
