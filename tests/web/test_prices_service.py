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
