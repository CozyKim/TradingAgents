"""yfinance wrapper with a small TTL cache.

In practice we expect ~32 entries (one per holding/inspect view × a few day
windows). No eviction is implemented; for personal-use scale the dict cannot
grow unbounded. Each entry key is ``(TICKER, days)`` and value is
``(expires_at_unix, PriceHistoryResponse)``.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from tradingagents.dataflows._yf_lock import YF_LOCK as _YF_LOCK
from tradingagents_web.schemas.price import PriceHistoryResponse, PricePoint

logger = logging.getLogger(__name__)

_TTL_SECONDS = 300  # 5 minutes
_CACHE: dict[tuple[str, int], tuple[float, PriceHistoryResponse]] = {}


def _yf_download(
    ticker: str,
    start: date,
    end: date,
    interval: str,
    progress: bool = False,
    auto_adjust: bool = True,
) -> Any:
    """Indirection so tests can monkeypatch yfinance.download cleanly.

    ``multi_level_index=False`` makes yfinance return flat columns
    (``Close``, ``Open``, ...) instead of the ``(field, ticker)`` MultiIndex
    that 0.2.40+ defaults to. The lock and the flat-column request are both
    necessary: the lock prevents ``shared._DFS`` from leaking another caller's
    ticker into our result, and the flat columns mean a single Close value
    is unambiguous even if a future yfinance version starts returning extra
    series.
    """
    import yfinance as yf

    with _YF_LOCK:
        return yf.download(
            ticker,
            start=start,
            end=end,
            interval=interval,
            progress=progress,
            auto_adjust=auto_adjust,
            multi_level_index=False,
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
        close_col = df["Close"]
        # Defense-in-depth: if a future code path leaks a multi-ticker frame
        # past the lock, prefer the requested ticker's column over a blind
        # iloc[:, 0] that would silently return another ticker's data.
        if hasattr(close_col, "columns"):
            if key[0] in close_col.columns:
                close_col = close_col[key[0]]
            else:
                logger.warning(
                    "prices: Close column for %s missing from frame %s; "
                    "discarding to avoid cross-ticker contamination",
                    key[0], list(close_col.columns),
                )
                close_col = None
        if close_col is not None:
            for ts, val in close_col.items():
                points.append(PricePoint(date=ts.date(), close=float(val)))
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
