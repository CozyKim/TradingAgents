"""yfinance wrapper with a small TTL cache.

In practice we expect ~32 entries (one per holding/inspect view × a few day
windows). No eviction is implemented; for personal-use scale the dict cannot
grow unbounded. Each entry key is ``(TICKER, days)`` and value is
``(expires_at_unix, PriceHistoryResponse)``.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from tradingagents_web.schemas.price import PriceHistoryResponse, PricePoint

logger = logging.getLogger(__name__)

_TTL_SECONDS = 300  # 5 minutes
_CACHE: dict[tuple[str, int], tuple[float, PriceHistoryResponse]] = {}
# yfinance.download is not thread-safe: concurrent calls share internal state
# and can return another ticker's frame. Serialize the network call only —
# cache hits stay lock-free.
_YF_LOCK = threading.Lock()


def _yf_download(
    ticker: str,
    start: date,
    end: date,
    interval: str,
    progress: bool = False,
    auto_adjust: bool = True,
) -> Any:
    """Indirection so tests can monkeypatch yfinance.download cleanly."""
    import yfinance as yf

    with _YF_LOCK:
        return yf.download(
            ticker,
            start=start,
            end=end,
            interval=interval,
            progress=progress,
            auto_adjust=auto_adjust,
        )


def get_price_history(ticker: str, days: int = 90) -> PriceHistoryResponse:
    """Return up to ``days`` of daily close prices for ``ticker``.

    Args:
        ticker: Stock symbol (case-insensitive).
        days: Look-back window in calendar days.

    Returns:
        PriceHistoryResponse with daily PricePoints sorted ascending.
    """
    key = (ticker.strip().upper(), days)
    now = time.time()
    cached = _CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]

    end = datetime.now(timezone.utc).date() + timedelta(days=1)
    start = end - timedelta(days=days)
    try:
        df = _yf_download(key[0], start=start, end=end, interval="1d")
    except Exception:  # noqa: BLE001
        logger.exception("yfinance download failed for %s", key[0])
        df = None

    points: list[PricePoint] = []
    last_close: float | None = None
    if df is not None and len(df) > 0 and "Close" in df.columns:
        for ts, row in df.iterrows():
            close = float(row["Close"])
            points.append(PricePoint(date=ts.date(), close=close))
        last_close = points[-1].close if points else None

    response = PriceHistoryResponse(
        ticker=key[0],
        points=points,
        last_close=last_close,
    )
    # Empty/failed responses are cached for the full TTL — acceptable at
    # personal-use scale; revisit if transient yfinance hiccups become
    # user-visible.
    _CACHE[key] = (now + _TTL_SECONDS, response)
    return response


def clear_cache() -> None:
    """Drop the in-memory cache (used by tests / settings reload)."""
    _CACHE.clear()
