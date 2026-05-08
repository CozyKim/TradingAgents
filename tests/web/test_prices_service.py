"""Tests for the price service (yfinance wrapper + TTL cache)."""
import pytest

from tradingagents_web.services import prices as svc


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
    values = [list(col) for col in zip(*close_by_ticker.values())]
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
