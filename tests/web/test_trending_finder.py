"""Unit tests for the TrendingSectorFinder pipeline (injected callables)."""

from datetime import date

from tradingagents_web.services.trending_finder import (
    build_seed_queries,
    search_recent,
)


def test_seed_queries_include_current_year_and_month_kr_and_en():
    queries = build_seed_queries(today=date(2026, 5, 30))
    joined = "\n".join(queries)
    # 한글 쿼리에 연·월이 박혀 있어야 한다
    assert "2026" in joined
    assert "5월" in joined
    # 영문 쿼리에 영문 월/연도가 있어야 한다
    assert "May 2026" in joined
    # 최소 한 개의 한글 쿼리와 한 개의 영문 쿼리
    assert any("투자" in q or "급등" in q or "테마" in q for q in queries)
    assert any("stock" in q.lower() or "sector" in q.lower() for q in queries)


def test_search_recent_passes_time_filter_and_returns_hits():
    calls = []

    def fake_tavily_search(query, **kwargs):
        calls.append((query, kwargs))
        return {
            "results": [
                {"title": "T", "url": "u", "content": "c", "published_date": "2026-05-28"}
            ]
        }

    hits = search_recent(
        "급등 섹터 2026", days=14, client_search=fake_tavily_search
    )
    assert hits and hits[0]["title"] == "T"
    # 최신성 파라미터가 Tavily 호출에 전달돼야 한다
    assert calls[0][1].get("topic") == "news"
    assert calls[0][1].get("days") == 14


def test_search_recent_swallows_errors_and_returns_empty():
    def boom(query, **kwargs):
        raise RuntimeError("network down")

    assert search_recent("x", days=7, client_search=boom) == []
