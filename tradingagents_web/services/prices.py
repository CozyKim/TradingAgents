"""yfinance wrapper with a small TTL cache.

In practice we expect ~32 entries (one per holding/inspect view × a few day
windows). No eviction is implemented; for personal-use scale the dict cannot
grow unbounded. Each entry key is ``(TICKER, days)`` and value is
``(expires_at_unix, PriceHistoryResponse)``.
"""
from __future__ import annotations

import logging
import math
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

from tradingagents.dataflows._yf_lock import YF_LOCK as _YF_LOCK
from tradingagents.dataflows._yf_lock import ensure_shared_yf_session
from tradingagents_web.schemas.price import PriceHistoryResponse, PricePoint

logger = logging.getLogger(__name__)

OHLCV_FIELDS: tuple[str, ...] = ("Open", "High", "Low", "Close", "Volume")


def _select_ticker_ohlcv(
    df: pd.DataFrame | None, ticker: str
) -> pd.DataFrame | None:
    """Return a flat OHLCV frame for ``ticker``, or None if unrecoverable.

    Handles two yfinance return shapes:
      - flat columns: ["Open","High","Low","Close","Volume"]
      - MultiIndex columns: [(field, ticker), ...]

    Defense-in-depth against ``multi_level_index=False`` being silently
    ignored or against multi-ticker frames leaking past the YF lock.
    """
    if df is None or len(df) == 0:
        return None

    # Case 2 (checked first): MultiIndex (field, ticker). Membership of top-
    # level field names also passes the flat-column check below, so route
    # MultiIndex frames here before the flat-column branch.
    if isinstance(df.columns, pd.MultiIndex):
        try:
            sub = df.xs(ticker, axis=1, level=1, drop_level=True)
        except KeyError:
            logger.warning("prices: ticker %s not in MultiIndex frame", ticker)
            return None
        if not all(f in sub.columns for f in OHLCV_FIELDS):
            return None
        return sub[list(OHLCV_FIELDS)]

    # Case 1: flat columns. Require the full OHLCV set.
    if all(f in df.columns for f in OHLCV_FIELDS):
        out = df
        for f in OHLCV_FIELDS:
            col = out[f]
            if hasattr(col, "columns"):  # accessor returned a DataFrame
                if ticker in col.columns:
                    out = out.assign(**{f: col[ticker]})
                else:
                    logger.warning(
                        "prices: %s missing from %s column for %s; aborting",
                        ticker, f, list(col.columns),
                    )
                    return None
        return out[list(OHLCV_FIELDS)]

    return None


def _row_is_valid(row: pd.Series) -> bool:
    """All OHLC fields must be finite. Volume may be NaN (treated as 0)."""
    for f in ("Open", "High", "Low", "Close"):
        v = row[f]
        if not pd.notna(v):
            return False
        try:
            if not math.isfinite(float(v)):
                return False
        except (TypeError, ValueError):
            return False
    return True


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

    ensure_shared_yf_session()
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
    sub = _select_ticker_ohlcv(df, key[0])
    if sub is not None:
        for ts, row in sub.iterrows():
            if not _row_is_valid(row):
                continue
            vol_raw = row["Volume"]
            try:
                vol_finite = pd.notna(vol_raw) and math.isfinite(float(vol_raw))
            except (TypeError, ValueError):
                vol_finite = False
            volume = int(float(vol_raw)) if vol_finite else 0
            points.append(PricePoint(
                date=ts.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=volume,
            ))
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
