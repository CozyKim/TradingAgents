"""Tests for the price service (yfinance wrapper + TTL cache)."""
import math

import pandas as pd
import pytest

from tradingagents_web.services import prices as svc
from tradingagents_web.services.prices import _select_ticker_ohlcv


@pytest.fixture(autouse=True)
def _clear_cache():
    svc._CACHE.clear()
    yield
    svc._CACHE.clear()


def test_get_history_returns_points(monkeypatch):
    captured = {"calls": 0}

    def fake_download(ticker, start, end, interval, progress=False, auto_adjust=True):
        captured["calls"] += 1
        import pandas as pd
        idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
        return pd.DataFrame({"Close": [180.0, 181.5]}, index=idx)

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    out = svc.get_price_history("aapl", days=5)
    assert out.ticker == "AAPL"
    assert len(out.points) == 2
    assert out.last_close == 181.5
    assert captured["calls"] == 1

    # Second call within TTL window does not re-download.
    again = svc.get_price_history("AAPL", days=5)
    assert again.last_close == 181.5
    assert captured["calls"] == 1


def test_get_history_empty_returns_no_last_close(monkeypatch):
    def fake_download(*a, **kw):
        import pandas as pd
        return pd.DataFrame({"Close": []}, index=pd.to_datetime([]))

    monkeypatch.setattr(svc, "_yf_download", fake_download)
    out = svc.get_price_history("XYZ", days=5)
    assert out.points == []
    assert out.last_close is None


def _multi_close_frame(close_by_ticker: dict[str, list[float]]):
    """Build a yfinance-style frame whose Close sub-frame has multiple ticker
    columns — the shape that previously slipped past iloc[:, 0]."""
    import pandas as pd
    idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
    values = [list(col) for col in zip(*close_by_ticker.values(), strict=False)]
    cols = pd.MultiIndex.from_product([["Close"], list(close_by_ticker)])
    return pd.DataFrame(values, index=idx, columns=cols)


def test_get_history_picks_requested_ticker_from_multicolumn_frame(monkeypatch):
    """Defense-in-depth: if yfinance leaks another ticker into our frame,
    select the requested ticker's column rather than iloc[:, 0]."""
    def fake_download(*a, **kw):
        # NFLX column comes first — iloc[:, 0] would have returned 88.27.
        return _multi_close_frame({"NFLX": [87.5, 88.27], "GOOGL": [395.0, 397.1]})

    monkeypatch.setattr(svc, "_yf_download", fake_download)
    out = svc.get_price_history("GOOGL", days=5)
    assert out.last_close == 397.1
    assert [p.close for p in out.points] == [395.0, 397.1]


def test_get_history_drops_frame_when_requested_ticker_missing(monkeypatch):
    """If the requested ticker is absent from the leaked frame, return None
    rather than caching another ticker's price under our key."""
    def fake_download(*a, **kw):
        return _multi_close_frame({"NFLX": [87.5, 88.27]})

    monkeypatch.setattr(svc, "_yf_download", fake_download)
    out = svc.get_price_history("GOOGL", days=5)
    assert out.points == []
    assert out.last_close is None


def _flat_ohlcv_frame() -> pd.DataFrame:
    idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
    return pd.DataFrame(
        {
            "Open": [180.0, 181.0],
            "High": [182.5, 183.2],
            "Low": [179.4, 180.6],
            "Close": [181.5, 182.7],
            "Volume": [12_345_678, 9_876_543],
        },
        index=idx,
    )


def _multi_ohlcv_frame(tickers: list[str]) -> pd.DataFrame:
    """yfinance MultiIndex shape: columns are (field, ticker)."""
    idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
    fields = ["Open", "High", "Low", "Close", "Volume"]
    cols = pd.MultiIndex.from_product([fields, tickers])
    data = {}
    for f in fields:
        for t in tickers:
            base = 100.0 if t == "AAPL" else 200.0
            offset = {"Open": 0, "High": 2, "Low": -1, "Close": 1, "Volume": 1_000}[f]
            data[(f, t)] = [base + offset, base + offset + 0.5]
    return pd.DataFrame(data, index=idx, columns=cols)


def test_select_flat_frame_returns_ohlcv_columns():
    df = _flat_ohlcv_frame()
    out = _select_ticker_ohlcv(df, "AAPL")
    assert out is not None
    assert list(out.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert list(out["Close"]) == [181.5, 182.7]


def test_select_multiindex_frame_picks_requested_ticker():
    df = _multi_ohlcv_frame(["NFLX", "AAPL"])
    out = _select_ticker_ohlcv(df, "AAPL")
    assert out is not None
    # AAPL base=100, Close offset=+1 → [101.0, 101.5]
    assert list(out["Close"]) == [101.0, 101.5]


def test_select_multiindex_frame_drops_when_ticker_missing():
    df = _multi_ohlcv_frame(["NFLX", "GOOGL"])
    assert _select_ticker_ohlcv(df, "AAPL") is None


def test_select_returns_none_for_empty_frame():
    assert _select_ticker_ohlcv(pd.DataFrame(), "AAPL") is None
    assert _select_ticker_ohlcv(None, "AAPL") is None  # type: ignore[arg-type]


def test_select_flat_frame_with_partial_columns_returns_none():
    """Open/Close만 있고 High/Low/Volume이 없으면 안전하게 폐기."""
    idx = pd.to_datetime(["2026-04-21"])
    df = pd.DataFrame({"Open": [1.0], "Close": [2.0]}, index=idx)
    assert _select_ticker_ohlcv(df, "AAPL") is None


def test_get_history_returns_ohlcv_points(monkeypatch):
    def fake(*a, **kw):
        return _flat_ohlcv_frame()

    monkeypatch.setattr(svc, "_yf_download", fake)
    out = svc.get_price_history("AAPL", days=5)
    assert len(out.points) == 2
    p0 = out.points[0]
    assert p0.open == 180.0
    assert p0.high == 182.5
    assert p0.low == 179.4
    assert p0.close == 181.5
    assert p0.volume == 12_345_678
    assert out.last_close == 182.7  # last close


def test_get_history_skips_rows_with_nan_ohlc(monkeypatch):
    def fake(*a, **kw):
        idx = pd.to_datetime(["2026-04-21", "2026-04-22", "2026-04-23"])
        return pd.DataFrame(
            {
                "Open":   [180.0, math.nan, 182.0],
                "High":   [182.0, 183.0,    184.0],
                "Low":    [179.0, 180.0,    181.0],
                "Close":  [181.0, 182.0,    183.0],
                "Volume": [10,    20,       30],
            },
            index=idx,
        )

    monkeypatch.setattr(svc, "_yf_download", fake)
    out = svc.get_price_history("AAPL", days=5)
    assert len(out.points) == 2
    assert [p.open for p in out.points] == [180.0, 182.0]
    assert out.last_close == 183.0


def test_get_history_skips_inf_close(monkeypatch):
    def fake(*a, **kw):
        idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
        return pd.DataFrame(
            {
                "Open":   [180.0, 181.0],
                "High":   [182.0, 183.0],
                "Low":    [179.0, 180.0],
                "Close":  [181.0, math.inf],
                "Volume": [10,    20],
            },
            index=idx,
        )

    monkeypatch.setattr(svc, "_yf_download", fake)
    out = svc.get_price_history("AAPL", days=5)
    assert len(out.points) == 1
    assert out.last_close == 181.0


def test_get_history_volume_nan_normalized_to_zero(monkeypatch):
    def fake(*a, **kw):
        idx = pd.to_datetime(["2026-04-21"])
        return pd.DataFrame(
            {
                "Open":   [180.0],
                "High":   [182.0],
                "Low":    [179.0],
                "Close":  [181.0],
                "Volume": [math.nan],
            },
            index=idx,
        )

    monkeypatch.setattr(svc, "_yf_download", fake)
    out = svc.get_price_history("XYZ", days=5)
    assert len(out.points) == 1
    assert out.points[0].volume == 0


def test_get_history_all_invalid_rows_returns_empty(monkeypatch):
    def fake(*a, **kw):
        idx = pd.to_datetime(["2026-04-21"])
        return pd.DataFrame(
            {
                "Open":   [math.nan],
                "High":   [math.nan],
                "Low":    [math.nan],
                "Close":  [math.nan],
                "Volume": [0],
            },
            index=idx,
        )

    monkeypatch.setattr(svc, "_yf_download", fake)
    out = svc.get_price_history("XYZ", days=5)
    assert out.points == []
    assert out.last_close is None
