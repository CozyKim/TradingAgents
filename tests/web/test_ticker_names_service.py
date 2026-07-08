"""Unit tests for the ticker → display-name resolver."""
from datetime import datetime, timedelta, timezone

import pytest

from tradingagents_web.models import TickerName
from tradingagents_web.schemas.ticker_search import TickerSearchResult
from tradingagents_web.services import ticker_names as svc


@pytest.fixture(autouse=True)
def _clear_miss_cache():
    """negative 캐시는 모듈 전역이라 테스트 간 격리가 필요하다."""
    svc._MISS.clear()
    yield
    svc._MISS.clear()


def _hit(ticker: str, name: str) -> TickerSearchResult:
    market = "KR" if ticker.endswith((".KS", ".KQ")) else "US"
    return TickerSearchResult(ticker=ticker, name=name, market=market)


class TestCanonical:
    def test_strips_korean_suffix(self):
        assert svc._canonical("005930.KS") == "005930"
        assert svc._canonical("035720.KQ") == "035720"

    def test_converts_class_share_dash_to_dot(self):
        # Naver는 BRK-B 를 모른다. BRK.B 로 물어야 한다.
        assert svc._canonical("brk-b") == "BRK.B"

    def test_uppercases_plain_ticker(self):
        assert svc._canonical(" aapl ") == "AAPL"

    def test_is_idempotent(self):
        # 질의어 생성과 비교 키를 겸하므로 두 번 적용해도 같아야 한다.
        for raw in ("005930.KS", "brk-b", " aapl "):
            once = svc._canonical(raw)
            assert svc._canonical(once) == once


class TestPickExact:
    def test_rejects_prefix_matches(self):
        # 실측: q=GS 는 한국 GS(078930)를 1위로 준다. items[0] 을 쓰면 안 된다.
        results = [_hit("078930.KS", "GS"), _hit("GS", "골드만삭스")]
        assert svc._pick_exact(results, "GS") == "골드만삭스"

    def test_matches_korean_ticker_through_suffix(self):
        # 응답 티커는 005930.KS, 질의어는 005930 — 양쪽을 정규화해 비교한다.
        results = [_hit("005930.KS", "삼성전자")]
        assert svc._pick_exact(results, "005930") == "삼성전자"

    def test_matches_class_share_from_either_spelling(self):
        # Yahoo 폴백은 원본 티커(BRK-B)를 want 로 넘긴다. 응답 심볼도 BRK-B 다.
        # want 에 _canonical 을 적용하지 않으면 여기서 조용히 None 이 된다.
        assert svc._pick_exact([_hit("BRK-B", "Berkshire Hathaway Inc.")], "BRK-B") == (
            "Berkshire Hathaway Inc."
        )
        # Naver 경로는 이미 정규화된 want 를 넘긴다. 양쪽 다 통해야 한다.
        assert svc._pick_exact([_hit("BRK.B", "버크셔 해서웨이 Class B")], "BRK.B") == (
            "버크셔 해서웨이 Class B"
        )

    def test_returns_none_when_no_exact_match(self):
        assert svc._pick_exact([_hit("AAPL", "애플")], "AA") is None


class TestResolveNames:
    async def test_uses_naver_first(self, db_session, monkeypatch):
        async def fake_naver(q):
            assert q == "AAPL"
            return [_hit("AAPL", "애플")]

        async def fake_yahoo(q):  # pragma: no cover - 호출되면 안 됨
            raise AssertionError("Naver가 성공하면 Yahoo를 부르지 않는다")

        monkeypatch.setattr(svc, "_search_naver", fake_naver)
        monkeypatch.setattr(svc, "_search_yahoo", fake_yahoo)

        assert await svc.resolve_names(["AAPL"], db_session) == {"AAPL": "애플"}
        assert db_session.get(TickerName, "AAPL").name == "애플"

    async def test_falls_back_to_yahoo(self, db_session, monkeypatch):
        async def fake_naver(q):
            return []

        async def fake_yahoo(q):
            assert q == "SMCI"
            return [_hit("SMCI", "Super Micro Computer, Inc.")]

        monkeypatch.setattr(svc, "_search_naver", fake_naver)
        monkeypatch.setattr(svc, "_search_yahoo", fake_yahoo)

        out = await svc.resolve_names(["SMCI"], db_session)
        assert out == {"SMCI": "Super Micro Computer, Inc."}

    async def test_omits_key_and_skips_db_on_total_failure(self, db_session, monkeypatch):
        async def empty(q):
            return []

        monkeypatch.setattr(svc, "_search_naver", empty)
        monkeypatch.setattr(svc, "_search_yahoo", empty)

        assert await svc.resolve_names(["^GSPC"], db_session) == {}
        assert db_session.get(TickerName, "^GSPC") is None

    async def test_negative_cache_prevents_second_upstream_call(self, db_session, monkeypatch):
        calls = {"n": 0}

        async def counting(q):
            calls["n"] += 1
            return []

        monkeypatch.setattr(svc, "_search_naver", counting)
        monkeypatch.setattr(svc, "_search_yahoo", counting)

        await svc.resolve_names(["NOPE"], db_session)
        first = calls["n"]
        await svc.resolve_names(["NOPE"], db_session)
        assert calls["n"] == first, "negative 캐시가 있으면 재조회하지 않는다"

    async def test_db_hit_skips_upstream(self, db_session, monkeypatch):
        db_session.add(TickerName(ticker="NVDA", name="엔비디아"))
        db_session.commit()

        async def boom(q):  # pragma: no cover
            raise AssertionError("DB 히트면 업스트림을 부르지 않는다")

        monkeypatch.setattr(svc, "_search_naver", boom)
        monkeypatch.setattr(svc, "_search_yahoo", boom)

        assert await svc.resolve_names(["nvda"], db_session) == {"NVDA": "엔비디아"}

    async def test_stale_row_is_refreshed_and_timestamp_advances(self, db_session, monkeypatch):
        old = datetime.now(timezone.utc) - timedelta(days=31)
        row = TickerName(ticker="AAPL", name="애플", created_at=old, updated_at=old)
        db_session.add(row)
        db_session.commit()

        async def fake_naver(q):
            return [_hit("AAPL", "애플")]  # 이름이 동일해도 updated_at 은 갱신돼야 한다

        monkeypatch.setattr(svc, "_search_naver", fake_naver)
        assert await svc.resolve_names(["AAPL"], db_session) == {"AAPL": "애플"}

        db_session.expire_all()
        fresh = db_session.get(TickerName, "AAPL").updated_at
        if fresh.tzinfo is None:
            fresh = fresh.replace(tzinfo=timezone.utc)
        assert fresh > old, "ORM이 UPDATE를 생략해도 updated_at 은 밀어줘야 한다"

    async def test_upstream_exception_is_swallowed(self, db_session, monkeypatch):
        import httpx

        async def boom(q):
            raise httpx.ConnectTimeout("upstream down")

        monkeypatch.setattr(svc, "_search_naver", boom)
        monkeypatch.setattr(svc, "_search_yahoo", boom)

        assert await svc.resolve_names(["AAPL"], db_session) == {}

    async def test_stale_row_survives_upstream_outage(self, db_session, monkeypatch):
        """채택안의 핵심 이득: 업스트림이 죽어도 DB에 있던 이름을 계속 서빙한다."""
        import httpx

        old = datetime.now(timezone.utc) - timedelta(days=31)
        db_session.add(TickerName(ticker="AAPL", name="애플", created_at=old, updated_at=old))
        db_session.commit()

        async def boom(q):
            raise httpx.ConnectTimeout("upstream down")

        monkeypatch.setattr(svc, "_search_naver", boom)
        monkeypatch.setattr(svc, "_search_yahoo", boom)

        assert await svc.resolve_names(["AAPL"], db_session) == {"AAPL": "애플"}

    async def test_dedupes_and_uppercases_input(self, db_session, monkeypatch):
        seen: list[str] = []

        async def fake_naver(q):
            seen.append(q)
            return [_hit("AAPL", "애플")]

        monkeypatch.setattr(svc, "_search_naver", fake_naver)
        out = await svc.resolve_names(["aapl", "AAPL", " aapl "], db_session)
        assert out == {"AAPL": "애플"}
        assert seen == ["AAPL"], "중복 티커는 한 번만 조회한다"

    async def test_empty_input_touches_nothing(self, db_session, monkeypatch):
        async def boom(q):  # pragma: no cover
            raise AssertionError("빈 입력이면 업스트림 없음")

        monkeypatch.setattr(svc, "_search_naver", boom)
        assert await svc.resolve_names([], db_session) == {}
