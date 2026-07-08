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


def test_names_requires_auth(client_unauth):
    resp = client_unauth.get("/api/tickers/names?tickers=AAPL")
    assert resp.status_code == 401


def test_names_returns_map(auth_client, monkeypatch):
    from tradingagents_web.services import ticker_names as names_svc

    async def fake_resolve(tickers, db):
        assert list(tickers) == ["AAPL", "005930.KS"]
        return {"AAPL": "애플", "005930.KS": "삼성전자"}

    monkeypatch.setattr(names_svc, "resolve_names", fake_resolve)
    resp = auth_client.get("/api/tickers/names?tickers=aapl,005930.ks")
    assert resp.status_code == 200
    assert resp.json() == {"names": {"AAPL": "애플", "005930.KS": "삼성전자"}}


def test_names_empty_query_skips_service(auth_client, monkeypatch):
    from tradingagents_web.services import ticker_names as names_svc

    async def boom(tickers, db):  # pragma: no cover
        raise AssertionError("빈 입력이면 서비스를 부르지 않는다")

    monkeypatch.setattr(names_svc, "resolve_names", boom)
    resp = auth_client.get("/api/tickers/names?tickers=")
    assert resp.status_code == 200
    assert resp.json() == {"names": {}}


def test_names_rejects_over_100_tickers(auth_client):
    many = ",".join(f"T{i}" for i in range(101))
    resp = auth_client.get(f"/api/tickers/names?tickers={many}")
    assert resp.status_code == 422


def test_names_omits_unresolved_tickers(auth_client, monkeypatch):
    from tradingagents_web.services import ticker_names as names_svc

    async def partial(tickers, db):
        return {"AAPL": "애플"}  # ^GSPC 는 생략

    monkeypatch.setattr(names_svc, "resolve_names", partial)
    resp = auth_client.get("/api/tickers/names?tickers=AAPL,^GSPC")
    assert resp.status_code == 200
    assert resp.json() == {"names": {"AAPL": "애플"}}
