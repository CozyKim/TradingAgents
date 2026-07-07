"""Tests for the ticker-search in-memory TTL+LRU cache."""
import pytest

from tradingagents_web.schemas.ticker_search import TickerSearchResult
from tradingagents_web.services import ticker_search as svc


@pytest.fixture(autouse=True)
def _clear_cache():
    svc._CACHE.clear()
    yield
    svc._CACHE.clear()


def _mk(ticker: str) -> list[TickerSearchResult]:
    return [TickerSearchResult(ticker=ticker, name=ticker, market="US")]


def test_put_get_roundtrip_and_key_normalization():
    svc._cache_put("Apple", _mk("AAPL"))
    assert svc._cache_get("  apple ")[0].ticker == "AAPL"   # type: ignore[index]  # trim+lower 정규화
    assert svc._cache_get("nope") is None


def test_ttl_expiry(monkeypatch):
    t = {"v": 1000.0}
    monkeypatch.setattr(svc, "_now", lambda: t["v"])
    svc._cache_put("q", _mk("AAPL"))
    t["v"] = 1000.0 + svc._CACHE_TTL + 1
    assert svc._cache_get("q") is None                      # 만료 후 miss


def test_lru_eviction():
    for i in range(svc._CACHE_MAX + 10):
        svc._cache_put(f"q{i}", _mk(f"T{i}"))
    assert len(svc._CACHE) == svc._CACHE_MAX                # 상한 유지
    assert svc._cache_get("q0") is None                     # 가장 오래된 것 축출
    assert svc._cache_get(f"q{svc._CACHE_MAX + 9}") is not None
