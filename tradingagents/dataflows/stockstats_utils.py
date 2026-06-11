import time
import logging

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError
from stockstats import wrap
from collections.abc import Callable
from typing import Annotated, TypeVar
import os
from .config import get_config
from ._yf_lock import YF_LOCK, ensure_shared_yf_session

logger = logging.getLogger(__name__)

T = TypeVar("T")


def yf_retry(func: Callable[[], T], max_retries: int = 3, base_delay: float = 2.0) -> T:
    """Execute a yfinance call serialized by YF_LOCK, with 429 backoff.

    yfinance raises YFRateLimitError on HTTP 429 responses but does not
    retry them internally. This wrapper adds retry logic specifically
    for rate limits. Other exceptions propagate immediately.

    The shared single-Curl session (see ``_yf_lock``) is unsafe under
    concurrent use, so the lock is acquired here — callers must NOT hold
    YF_LOCK around yf_retry (it is non-reentrant). Backoff sleeps happen
    outside the lock so other callers can proceed.
    """
    ensure_shared_yf_session()
    for attempt in range(max_retries + 1):
        try:
            with YF_LOCK:
                return func()
        except YFRateLimitError:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Yahoo Finance rate limited, retrying in {delay:.0f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                raise
    raise AssertionError("unreachable: final attempt either returns or raises")


def _clean_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize a stock DataFrame for stockstats: parse dates, drop invalid rows, fill price gaps."""
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])

    price_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in data.columns]
    data[price_cols] = data[price_cols].apply(pd.to_numeric, errors="coerce")
    data = data.dropna(subset=["Close"])
    data[price_cols] = data[price_cols].ffill().bfill()

    return data


def load_ohlcv(symbol: str, curr_date: str) -> pd.DataFrame:
    """Fetch OHLCV data with caching, filtered to prevent look-ahead bias.

    Downloads 15 years of data up to today and caches per symbol. On
    subsequent calls the cache is reused. Rows after curr_date are
    filtered out so backtests never see future prices.
    """
    config = get_config()
    curr_date_dt = pd.to_datetime(curr_date)

    # Cache uses a fixed window (15y to today) so one file per symbol
    today_date = pd.Timestamp.today()
    start_date = today_date - pd.DateOffset(years=5)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = today_date.strftime("%Y-%m-%d")

    os.makedirs(config["data_cache_dir"], exist_ok=True)
    data_file = os.path.join(
        config["data_cache_dir"],
        f"{symbol}-YFin-data-{start_str}-{end_str}.csv",
    )

    # Treat header-only / empty cache files as missing. yfinance occasionally
    # returns an empty frame (rate limit, market-open transient, bad ticker),
    # which we used to persist as a 0-row CSV and then re-read forever — every
    # downstream indicator would then silently report "Not a trading day".
    cache_usable = (
        os.path.exists(data_file) and os.path.getsize(data_file) > 64
    )

    data: pd.DataFrame | None = None
    if cache_usable:
        cached = pd.read_csv(data_file, on_bad_lines="skip", encoding="utf-8")
        # Reject caches written before the YF_LOCK fix that captured a
        # multi-ticker frame. The original CSV header was "Close,Close,
        # High,High,...", which pandas read_csv silently renames to
        # "Close,Close.1,High,High.1,..." — so we check for the suffix
        # rather than duplicated().
        contaminated = any(
            isinstance(c, str) and any(
                c.startswith(f"{base}.") and c[len(base) + 1:].isdigit()
                for base in ("Open", "High", "Low", "Close", "Volume", "Adj Close")
            )
            for c in cached.columns
        )
        if contaminated:
            logger.warning(
                "discarding contaminated cache for %s (%s) — multi-ticker columns %s; refetching",
                symbol, data_file, list(cached.columns),
            )
            try:
                os.remove(data_file)
            except OSError:
                pass
        else:
            data = cached

    if data is None:
        # Serialization against the web price/fx services happens inside
        # yf_retry via the shared YF_LOCK — yfinance is not thread-safe
        # (module-level shared._DFS leaks between concurrent callers), and
        # the shared single-Curl session must never be used concurrently.
        raw = yf_retry(lambda: yf.download(
            symbol,
            start=start_str,
            end=end_str,
            multi_level_index=False,
            progress=False,
            auto_adjust=True,
        ))
        if raw is None or raw.empty:
            logger.warning(
                "yfinance returned no rows for %s [%s..%s]; skipping cache write",
                symbol, start_str, end_str,
            )
            return pd.DataFrame()
        fetched: pd.DataFrame = raw.reset_index()
        fetched.to_csv(data_file, index=False, encoding="utf-8")
        data = fetched

    data = _clean_dataframe(data)

    # Filter to curr_date to prevent look-ahead bias in backtesting
    data = data[data["Date"] <= curr_date_dt]

    return data


def filter_financials_by_date(data: pd.DataFrame, curr_date: str) -> pd.DataFrame:
    """Drop financial statement columns (fiscal period timestamps) after curr_date.

    yfinance financial statements use fiscal period end dates as columns.
    Columns after curr_date represent future data and are removed to
    prevent look-ahead bias.
    """
    if not curr_date or data.empty:
        return data
    cutoff = pd.Timestamp(curr_date)
    mask = pd.to_datetime(data.columns, errors="coerce") <= cutoff
    return data.loc[:, mask]


class StockstatsUtils:
    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
    ):
        data = load_ohlcv(symbol, curr_date)
        if data.empty:
            return f"N/A: No price data available for {symbol}"
        df = wrap(data)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        curr_date_str = pd.to_datetime(curr_date).strftime("%Y-%m-%d")

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date_str)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"
