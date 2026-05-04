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


def test_cache_hit_skips_download(monkeypatch):
    captured = {"calls": 0}

    def fake_download(ticker, period="5d", interval="1d", **kw):
        captured["calls"] += 1
        import pandas as pd
        idx = pd.to_datetime(["2026-05-05"])
        return pd.DataFrame({"Close": [1382.1]}, index=idx)

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    first = svc.get_usd_krw_rate()
    second = svc.get_usd_krw_rate()
    assert first.rate == 1382.1
    assert second.rate == 1382.1
    assert captured["calls"] == 1


def test_yfinance_failure_no_cache_returns_null_rate(monkeypatch):
    def fake_download(*a, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    out = svc.get_usd_krw_rate()
    assert out.rate is None
    assert out.as_of is None
    assert out.pair == "USDKRW"


def test_yfinance_failure_with_prior_cache_returns_stale(monkeypatch):
    # Prime the cache with a successful call.
    def good(ticker, period="5d", interval="1d", **kw):
        import pandas as pd
        idx = pd.to_datetime(["2026-05-05"])
        return pd.DataFrame({"Close": [1382.1]}, index=idx)

    monkeypatch.setattr(svc, "_yf_download", good)
    primed = svc.get_usd_krw_rate()
    assert primed.rate == 1382.1

    # Force the cache to expire so the next call re-downloads, then fail.
    svc._CACHE = (0, primed)

    def boom(*a, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(svc, "_yf_download", boom)

    stale = svc.get_usd_krw_rate()
    assert stale.rate == 1382.1  # served from prior cache despite TTL expiry


def test_empty_dataframe_returns_null_rate(monkeypatch):
    def fake_download(*a, **kw):
        import pandas as pd
        return pd.DataFrame({"Close": []}, index=pd.to_datetime([]))

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    out = svc.get_usd_krw_rate()
    assert out.rate is None
    assert out.as_of is None
