"""Unit tests for the TrendingSectorFinder pipeline (injected callables)."""

import asyncio
import json
from datetime import date

from tradingagents_web.services.event_bus import EventBus
from tradingagents_web.services.trending_finder import (
    FakeTrendingFinder,
    TrendingSectorFinder,
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


def test_search_recent_returns_empty_when_no_api_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert search_recent("x", days=7) == []


def _drain_history(bus: EventBus, job_id: str):
    return [(e.type, e.data) for e in bus.history(job_id)]


def test_fake_finder_emits_stage_events_and_returns_sectors():
    bus = EventBus()
    finder = FakeTrendingFinder(bus)
    sectors = asyncio.run(finder.find("job-1"))
    assert len(sectors) >= 1
    # 점수 내림차순 정렬
    scores = [s.hotness_score for s in sectors]
    assert scores == sorted(scores, reverse=True)
    # discover/enrich/score/rank 진행 이벤트가 발행됐다 (done/finish은 호출자 책임)
    stages = {d.get("stage") for t, d in _drain_history(bus, "job-1") if t == "progress"}
    assert {"discover", "enrich", "score", "rank"} <= stages


def test_real_finder_pipeline_with_injected_callables():
    bus = EventBus()

    def fake_search(query, *, days, client_search=None):
        return [{"title": "온디바이스 AI 급부상", "url": "u", "snippet": "...", "published_date": "2026-05-29"}]

    def fake_llm_json(prompt: str) -> str:
        return json.dumps(
            {
                "themes": [
                    {
                        "name": "온디바이스 AI",
                        "description": "단말 추론 가속",
                        "keywords": ["NPU", "on-device"],
                        "tickers": ["AAPL", "QCOM"],
                        "web_trend": 80,
                    }
                ]
            },
            ensure_ascii=False,
        )

    def fake_social(ticker: str):
        return {"bullish": 8, "bearish": 2, "total_messages": 40}

    def fake_momentum(ticker: str):
        return {"avg_return_pct": 6.0}

    finder = TrendingSectorFinder(
        bus,
        llm_json=fake_llm_json,
        search_fn=fake_search,
        social_fn=fake_social,
        momentum_fn=fake_momentum,
        today=date(2026, 5, 30),
    )
    sectors = asyncio.run(finder.find("job-2"))
    assert len(sectors) == 1
    s = sectors[0]
    assert s.name == "온디바이스 AI"
    assert s.signals.web_trend == 80
    assert s.signals.sentiment == 80.0  # 8/(8+2)*100
    assert 0 <= s.hotness_score <= 100
    assert s.rationale  # 비어있지 않음
