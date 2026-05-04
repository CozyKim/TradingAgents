"""Tests for the FX service (yfinance KRW=X wrapper + 24h TTL cache)."""
import pytest

from tradingagents_web.services import fx as svc


@pytest.fixture(autouse=True)
def _clear_cache():
    svc.clear_cache()
    yield
    svc.clear_cache()


def test_get_rate_returns_last_close(monkeypatch):
    captured = {"calls": 0}

    def fake_download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True):
        captured["calls"] += 1
        import pandas as pd
        idx = pd.to_datetime(["2026-05-04", "2026-05-05"])
        return pd.DataFrame({"Close": [1370.5, 1382.1]}, index=idx)

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    out = svc.get_usd_krw_rate()
    assert out.pair == "USDKRW"
    assert out.rate == 1382.1
    assert out.as_of.isoformat() == "2026-05-05"
    assert captured["calls"] == 1
