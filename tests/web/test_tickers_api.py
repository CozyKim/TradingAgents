"""Integration tests for the /api/tickers/search and /api/tickers/names endpoints."""

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


def test_names_dedupes_before_limit_check(auth_client, monkeypatch):
    """dedupe가 100개 상한 계산보다 먼저 일어난다.

    동일 티커를 150번 보내도 dedupe 후에는 1개이므로 200이어야 하고, 서비스에
    넘어가는 리스트도 정확히 길이 1이어야 한다. 쿼리 문자열 길이는 약 750자로
    256자보다 커서, ``_MAX_TICKERS_LEN`` 이 실수로 축소되는 mutation도 함께 잡는다.
    """
    from tradingagents_web.services import ticker_names as names_svc

    async def fake_resolve(tickers, db):
        assert list(tickers) == ["AAPL"]
        return {"AAPL": "애플"}

    monkeypatch.setattr(names_svc, "resolve_names", fake_resolve)
    many = ",".join(["AAPL"] * 150)
    assert 256 < len(many) < 2048
    resp = auth_client.get(f"/api/tickers/names?tickers={many}")
    assert resp.status_code == 200
    assert resp.json() == {"names": {"AAPL": "애플"}}


def test_names_accepts_exactly_100_tickers(auth_client, monkeypatch):
    """서로 다른 티커 정확히 100개(경계값)는 통과해야 한다.

    ``len(wanted) > _MAX_TICKERS`` 가 ``>=`` 로 뒤바뀌는 off-by-one mutation이
    들어오면 100개에서도 422가 나므로 이 테스트가 깨진다.
    """
    from tradingagents_web.services import ticker_names as names_svc

    async def fake_resolve(tickers, db):
        assert len(list(tickers)) == 100
        return {}

    monkeypatch.setattr(names_svc, "resolve_names", fake_resolve)
    many = ",".join(f"T{i}" for i in range(100))
    resp = auth_client.get(f"/api/tickers/names?tickers={many}")
    assert resp.status_code == 200


def test_names_normalizes_whitespace_and_case(auth_client, monkeypatch):
    """공백·대소문자가 섞인 입력이 하나의 표준형 티커로 정리된다.

    ``t.strip().upper()`` 에서 ``strip()`` 이 빠지는 mutation이 들어오면 " AAPL"과
    "AAPL "이 서로 다른 키로 남아 dedupe 되지 않고, 서비스가 받는 리스트 길이도
    1이 아니게 되어 이 테스트가 깨진다.
    """
    from tradingagents_web.services import ticker_names as names_svc

    async def fake_resolve(tickers, db):
        assert list(tickers) == ["AAPL"]
        return {"AAPL": "애플"}

    monkeypatch.setattr(names_svc, "resolve_names", fake_resolve)
    resp = auth_client.get("/api/tickers/names", params={"tickers": " aapl , AAPL "})
    assert resp.status_code == 200
    assert resp.json() == {"names": {"AAPL": "애플"}}


def test_names_rejects_over_100_tickers_with_exact_detail_message(auth_client):
    """100개 초과 시 detail이 FastAPI의 list 형태가 아니라 우리 문자열 메시지와 정확히 일치한다."""
    many = ",".join(f"T{i}" for i in range(101))
    resp = auth_client.get(f"/api/tickers/names?tickers={many}")
    assert resp.status_code == 422
    assert resp.json()["detail"] == "최대 100개의 티커만 한 번에 조회할 수 있습니다."


def test_names_rejects_over_max_length_with_string_detail(auth_client):
    """쿼리 문자열 길이 초과 시에도 detail은 문자열이어야 한다 (FastAPI의 list[dict]가 아님).

    ``Query(max_length=...)`` 를 되살리는 회귀가 들어오면 FastAPI 자체 검증이
    ``detail`` 을 ``list[dict]`` 로 내므로 이 테스트가 깨진다.
    """
    too_long = "A" * 3000
    resp = auth_client.get(f"/api/tickers/names?tickers={too_long}")
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, str)
    assert detail == "티커 목록 문자열이 너무 깁니다 (최대 2048자)."


def test_names_db_cache_hit_skips_network(app_with_test_db, monkeypatch):
    """실제 resolve_names 를 태워 DB 캐시 히트만으로 응답이 나옴을 고정한다.

    다른 /names 테스트는 전부 resolve_names 자체를 fake로 교체하므로, resolve_names가
    (동기 함수로 리팩터링되는 등) await 계약을 깨거나 Depends(get_db) 배선이 끊겨도
    잡아내지 못한다. 이 테스트만 resolve_names를 건드리지 않고 ticker_names 테이블에
    행을 미리 심어 DB 캐시 히트 경로를 실제로 태운다. _search_naver/_search_yahoo를
    "호출되면 AssertionError"로 패치해 네트워크를 전혀 안 탐을 강제한다.
    """
    from fastapi.testclient import TestClient

    from tradingagents_web.auth import create_session
    from tradingagents_web.config import Settings
    from tradingagents_web.models import TickerName, User
    from tradingagents_web.services import ticker_names as names_svc

    async def boom(*args, **kwargs):
        raise AssertionError("DB 캐시 히트만으로 끝나야 하는데 업스트림을 불렀다")

    monkeypatch.setattr(names_svc, "_search_naver", boom)
    monkeypatch.setattr(names_svc, "_search_yahoo", boom)

    app, TestSessionLocal = app_with_test_db
    settings = Settings()

    db = TestSessionLocal()
    try:
        user = User(password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
        # updated_at 기본값(utcnow)이 방금이므로 30일 이내 = DB 캐시 히트로 취급된다.
        db.add(TickerName(ticker="AAPL", name="애플"))
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    client.cookies.set(settings.session_cookie_name, token)
    resp = client.get("/api/tickers/names?tickers=AAPL")
    assert resp.status_code == 200
    assert resp.json() == {"names": {"AAPL": "애플"}}
