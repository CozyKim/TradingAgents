"""yfinance USD/KRW wrapper with a 24-hour TTL cache.

The cache holds at most one entry (single currency pair). yfinance.download
is not thread-safe, so every yfinance call in the process must acquire the
shared YF_LOCK; the lock lives in tradingagents.dataflows._yf_lock so the
analysis pipeline can share it too.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from typing import Any

from tradingagents.dataflows._yf_lock import YF_LOCK, ensure_shared_yf_session
from tradingagents_web.schemas.fx import FxRate

logger = logging.getLogger(__name__)

_TTL_SECONDS = 24 * 3600
_CACHE: tuple[float, FxRate] | None = None


def _yf_download(ticker: str, period: str = "5d", interval: str = "1d") -> Any:
    """Indirection so tests can monkeypatch this module directly.

    ``multi_level_index=False`` keeps the columns flat (``Close`` is a
    Series rather than a single-column DataFrame). YF_LOCK serializes all
    yfinance access in the process so concurrent calls cannot leak frames.
    """
    import yfinance as yf

    ensure_shared_yf_session()
    with YF_LOCK:
        return yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            multi_level_index=False,
        )


def _extract_last_close(df: Any) -> tuple[float | None, date | None]:
    """Return (rate, as_of) from a yfinance DataFrame, skipping NaN rows."""
    if df is None or len(df) == 0 or "Close" not in df.columns:
        return None, None
    close = df["Close"]
    # Defensive: with the lock + multi_level_index=False this should always
    # be a Series, but guard against a future caller bypassing the lock and
    # leaving a multi-ticker frame in shared._DFS.
    if hasattr(close, "columns"):
        return None, None
    series = close.dropna()
    if series.empty:
        return None, None
    last_ts = series.index[-1]
    return float(series.iloc[-1]), last_ts.date()


def get_usd_krw_rate() -> FxRate:
    """USD/KRW spot rate. 24h TTL cache; falls back to stale cache on error."""
    global _CACHE
    now = time.time()
    cached = _CACHE
    if cached and cached[0] > now:
        return cached[1]

    fetched_at = datetime.now(timezone.utc)
    try:
        df = _yf_download("KRW=X")
        rate, as_of = _extract_last_close(df)
        result = FxRate(
            pair="USDKRW", rate=rate, as_of=as_of, fetched_at=fetched_at,
        )
    except Exception:  # noqa: BLE001
        logger.exception("yfinance KRW=X download failed")
        if cached is not None:
            return cached[1]
        result = FxRate(
            pair="USDKRW", rate=None, as_of=None, fetched_at=fetched_at,
        )

    _CACHE = (now + _TTL_SECONDS, result)
    return result


def clear_cache() -> None:
    """Drop the in-memory cache (used by tests)."""
    global _CACHE
    _CACHE = None
