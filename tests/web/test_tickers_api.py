"""Integration tests for the /api/tickers/search endpoint."""

from tradingagents_web.schemas.ticker_search import TickerSearchResult
from tradingagents_web.services import ticker_search as svc


def test_search_requires_auth(client_unauth):
    resp = client_unauth.get("/api/tickers/search?q=nvidia")
    assert resp.status_code == 401


def test_search_returns_results(auth_client, monkeypatch):
    async def fake_search(query):
        assert query == "nvidia"
        return [TickerSearchResult(ticker="NVDA", name="NVIDIA Corporation", market="US", exchange="NMS")]

    monkeypatch.setattr(svc, "search_tickers", fake_search)
    resp = auth_client.get("/api/tickers/search?q=nvidia")
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0] == {
        "ticker": "NVDA",
        "name": "NVIDIA Corporation",
        "market": "US",
        "exchange": "NMS",
    }


def test_search_empty_query(auth_client, monkeypatch):
    async def fake_search(query):
        return []

    monkeypatch.setattr(svc, "search_tickers", fake_search)
    resp = auth_client.get("/api/tickers/search?q=")
    assert resp.status_code == 200
    assert resp.json() == {"results": []}
