"""Tests for ticker search routing/cache/fallback orchestration."""
import httpx
import pytest

from tradingagents_web.schemas.ticker_search import TickerSearchResult
from tradingagents_web.services import ticker_search as svc


@pytest.fixture(autouse=True)
def _clear_cache():
    svc._CACHE.clear()
    yield
    svc._CACHE.clear()


def test_has_hangul():
    assert svc._has_hangul("삼성전자") is True
    assert svc._has_hangul("nvidia") is False
    assert svc._has_hangul("005930.KS") is False


async def test_routes_hangul_to_naver_english_to_yahoo(monkeypatch):
    calls = {"naver": 0, "yahoo": 0}

    async def fake_naver(q):
        calls["naver"] += 1
        return [TickerSearchResult(ticker="005930.KS", name="삼성전자", market="KR")]

    async def fake_yahoo(q):
        calls["yahoo"] += 1
        return [TickerSearchResult(ticker="NVDA", name="NVIDIA", market="US")]

    monkeypatch.setattr(svc, "_search_naver", fake_naver)
    monkeypatch.setattr(svc, "_search_yahoo", fake_yahoo)

    kr = await svc.search_tickers("삼성전자")
    assert kr[0].ticker == "005930.KS" and calls == {"naver": 1, "yahoo": 0}

    us = await svc.search_tickers("nvidia")
    assert us[0].ticker == "NVDA" and calls == {"naver": 1, "yahoo": 1}


async def test_empty_query_returns_empty_no_call(monkeypatch):
    async def boom(q):  # 호출되면 실패
        raise AssertionError("should not be called")

    monkeypatch.setattr(svc, "_search_yahoo", boom)
    monkeypatch.setattr(svc, "_search_naver", boom)
    assert await svc.search_tickers("   ") == []


async def test_result_is_cached(monkeypatch):
    calls = {"n": 0}

    async def fake_yahoo(q):
        calls["n"] += 1
        return [TickerSearchResult(ticker="NVDA", name="NVIDIA", market="US")]

    monkeypatch.setattr(svc, "_search_yahoo", fake_yahoo)
    await svc.search_tickers("nvidia")
    await svc.search_tickers("NVIDIA")   # 정규화 키 동일 → 캐시 히트
    assert calls["n"] == 1


async def test_upstream_failure_returns_empty(monkeypatch):
    async def fail(q):
        raise httpx.ConnectTimeout("boom")

    monkeypatch.setattr(svc, "_search_yahoo", fail)
    assert await svc.search_tickers("nvidia") == []
