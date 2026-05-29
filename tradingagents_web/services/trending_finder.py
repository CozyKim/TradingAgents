"""Hot-sector (trending) discovery service.

Pipeline: discover (recency-filtered KR+EN web search -> LLM theme extraction)
-> enrich (StockTwits + price momentum per theme ticker) -> score -> rank.

External dependencies (web search, social, price) are injected as callables
so the pipeline is deterministic under test. Network/LLM failures degrade to
empty/zeroed signals rather than raising — a trending scan must never crash.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import Callable
from datetime import date
from typing import Any

from tradingagents_web.schemas.trending import TrendingSector, TrendingSignals
from tradingagents_web.services.event_bus import AnalysisEvent, EventBus
from tradingagents_web.services.trending_score import (
    momentum_score,
    sentiment_score,
    volume_score,
    weighted_hotness,
)

logger = logging.getLogger(__name__)

# Tickers come from LLM output and flow into outbound HTTP (yfinance / StockTwits).
# Accept only plausible symbols; drop anything else.
_TICKER_RE = re.compile(r"^[A-Za-z.\-]{1,8}$")

# Number of recency-filtered web searches per scan (natural budget cap —
# there is no ReAct loop here, just a fixed seed-query set).
_MAX_SEARCHES = 6
# Tavily recency window (days) for trending discovery.
_SEARCH_DAYS = 14

_EN_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def build_seed_queries(today: date) -> list[str]:
    """Build KR + EN seed queries anchored to the current year/month.

    Args:
        today: The scan's anchor date (injected for deterministic tests).

    Returns:
        A list of search query strings mixing Korean and English so both
        Korean and US trending themes surface.
    """
    y = today.year
    m_kr = f"{today.month}월"
    m_en = f"{_EN_MONTHS[today.month - 1]} {y}"
    return [
        f"{y}년 {m_kr} 지금 뜨는 투자 테마 주식",
        f"{y}년 {m_kr} 급등 섹터 종목",
        f"{y}년 {m_kr} 이번 주 화제의 종목 커뮤니티",
        f"trending stock themes {m_en}",
        f"hottest market sectors {m_en} retail investors",
        f"stocks reddit wallstreetbets trending {m_en}",
    ]


def search_recent(
    query: str,
    *,
    days: int,
    client_search: Callable[..., dict] | None = None,
) -> list[dict[str, Any]]:
    """Run one recency-filtered Tavily search; never raises.

    Args:
        query: The search query.
        days: Recency window passed to Tavily (topic="news").
        client_search: Injectable Tavily ``client.search`` (tests pass a fake).
            When None, a real TavilyClient is constructed from TAVILY_API_KEY.

    Returns:
        List of {title, url, snippet, published_date}. Empty on any failure
        or missing API key.
    """
    try:
        if client_search is None:
            api_key = os.environ.get("TAVILY_API_KEY")
            if not api_key:
                logger.warning("TAVILY_API_KEY not set; search_recent returning []")
                return []
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            client_search = client.search
        raw = client_search(
            query,
            max_results=5,
            search_depth="advanced",
            topic="news",
            days=days,
        )
    except Exception:  # noqa: BLE001 — search must never crash a scan
        logger.exception("trending search_recent failed for %r", query)
        return []

    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
            "published_date": r.get("published_date", ""),
        }
        for r in raw.get("results", [])
    ]


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

# How many top themes to return.
_TOP_N = 6


def _progress(bus: EventBus, job_id: str, stage: str, **extra: Any) -> None:
    bus.publish(job_id, AnalysisEvent(type="progress", data={"stage": stage, **extra}))


def _build_discover_prompt(today: date, snippets: list[dict]) -> str:
    """Prompt the LLM to extract 5~8 fresh themes as strict JSON.

    Args:
        today: Anchor date, surfaced to the model so it can exclude stale items.
        snippets: Recency-filtered search hits to ground the extraction.

    Returns:
        A prompt string instructing the model to answer with strict JSON only.
    """
    lines = [f"- [{s.get('published_date','?')}] {s['title']}: {s['snippet']}" for s in snippets]
    corpus = "\n".join(lines) if lines else "(검색 결과 없음)"
    return (
        f"오늘 날짜: {today.isoformat()}.\n"
        "아래는 최근 웹/뉴스 검색 결과다. 지금 시장에서 '핫한' 신규 투자 테마를 "
        "5~8개 발굴하라. 수개월 지난 오래된 테마/뉴스는 제외한다.\n\n"
        f"{corpus}\n\n"
        "다음 JSON 스키마로만 답하라(코드블록·설명 금지):\n"
        '{"themes":[{"name":"한글 테마명","description":"한 줄 설명",'
        '"keywords":["k1","k2"],"tickers":["TICK1","TICK2"],"web_trend":0-100}]}'
    )


def _parse_themes(raw: str) -> list[dict]:
    """Parse the LLM JSON; tolerate accidental code fences / prose.

    Extracts the outermost {...} span, so a code fence or leading prose
    around the JSON object does not break parsing.

    Args:
        raw: The model's raw text response.

    Returns:
        The list under the ``themes`` key, or [] if absent/not a list.
    """
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return []
    data = json.loads(raw[start : end + 1])
    themes = data.get("themes", [])
    return themes if isinstance(themes, list) else []


def _rationale(web_trend: float, vol: float, sent: float, mom: float) -> str:
    """One-line Korean explanation highlighting the strongest signals.

    Args:
        web_trend: Web-trend score 0~100.
        vol: Community-volume score 0~100.
        sent: Sentiment score 0~100.
        mom: Momentum score 0~100.

    Returns:
        A short Korean phrase naming the signals above 60, or a neutral note.
    """
    parts = []
    if web_trend >= 60:
        parts.append("웹·뉴스에서 화제성↑")
    if vol >= 60:
        parts.append("커뮤니티 언급량 많음")
    if sent >= 60:
        parts.append("상승 감성 우세")
    if mom >= 60:
        parts.append("가격·거래량 모멘텀 양호")
    return ", ".join(parts) if parts else "신호가 고르게 분포"


# ---------------------------------------------------------------------------
# Main finder classes
# ---------------------------------------------------------------------------


class TrendingSectorFinder:
    """Discovers hot themes from recency-filtered search + per-ticker signals.

    Args:
        bus: EventBus to publish stage-progress events to.
        llm_json: Callable(prompt:str)->str returning the model's raw text.
        search_fn: Callable(query, *, days, client_search=None)->list[dict].
        social_fn: Callable(ticker)->{"bullish","bearish","total_messages"}.
        momentum_fn: Callable(ticker)->{"avg_return_pct": float}.
        today: Anchor date for recency (injected for tests).
    """

    def __init__(
        self,
        bus: EventBus,
        *,
        llm_json: Callable[[str], str],
        search_fn: Callable[..., list[dict]],
        social_fn: Callable[[str], dict],
        momentum_fn: Callable[[str], dict],
        today: date,
    ) -> None:
        self.bus = bus
        self.llm_json = llm_json
        self.search_fn = search_fn
        self.social_fn = social_fn
        self.momentum_fn = momentum_fn
        self.today = today

    async def find(self, job_id: str) -> list[TrendingSector]:
        """Run the 4-stage pipeline, emitting progress; never raises.

        Individual malformed themes or scoring failures are skipped with a
        warning so a single bad LLM item does not abort the entire scan.
        Returns whatever scored successfully — possibly an empty list.

        Args:
            job_id: EventBus run-id to publish progress under.

        Returns:
            Up to _TOP_N themes sorted by hotness descending.
        """
        # 1) discover
        _progress(self.bus, job_id, "discover", message="웹 검색 중…")
        snippets: list[dict] = []
        for query in build_seed_queries(self.today)[:_MAX_SEARCHES]:
            snippets.extend(
                await asyncio.to_thread(self.search_fn, query, days=_SEARCH_DAYS)
            )
        themes = await self._extract_themes(snippets)

        # 2) enrich
        enriched: list[TrendingSector] = []
        for i, theme in enumerate(themes, start=1):
            _progress(
                self.bus, job_id, "enrich",
                progress=f"{i}/{len(themes)}",
                message="종목 신호 수집 중…",
            )
            if not isinstance(theme, dict):
                logger.warning("skipping non-dict theme: %r", theme)
                continue
            try:
                enriched.append(await asyncio.to_thread(self._score_theme, theme))
            except Exception:  # noqa: BLE001 — skip a bad theme, keep the rest
                logger.exception("scoring theme failed; skipping: %r", theme.get("name"))

        # 3) score (already computed per theme) + 4) rank
        _progress(self.bus, job_id, "score", message="점수 계산 중…")
        enriched.sort(key=lambda s: s.hotness_score, reverse=True)
        ranked = enriched[:_TOP_N]
        _progress(self.bus, job_id, "rank", count=len(ranked))
        return ranked

    async def _extract_themes(self, snippets: list[dict]) -> list[dict]:
        """Prompt the LLM for themes, parsing JSON with one retry on failure.

        Args:
            snippets: Recency-filtered search hits to ground the extraction.

        Returns:
            Parsed theme dicts, or [] if both attempts fail.
        """
        prompt = _build_discover_prompt(self.today, snippets)
        for attempt in range(2):  # 1 retry on parse failure
            try:
                raw = await asyncio.to_thread(self.llm_json, prompt)
                return _parse_themes(raw)
            except Exception:  # noqa: BLE001
                logger.warning("theme JSON parse failed (attempt %d)", attempt + 1)
        return []

    def _score_theme(self, theme: dict) -> TrendingSector:
        tickers = [
            t for t in (theme.get("tickers") or [])
            if isinstance(t, str) and _TICKER_RE.match(t)
        ][:3]
        bullish = bearish = total_msgs = 0
        returns: list[float] = []
        for tk in tickers:
            try:
                soc = self.social_fn(tk)
                bullish += int(soc.get("bullish", 0))
                bearish += int(soc.get("bearish", 0))
                total_msgs += int(soc.get("total_messages", 0))
            except Exception:  # noqa: BLE001 — degrade to zero
                logger.debug("social_fn failed for %s", tk)
            try:
                returns.append(float(self.momentum_fn(tk).get("avg_return_pct", 0.0)))
            except Exception:  # noqa: BLE001
                logger.debug("momentum_fn failed for %s", tk)

        try:
            web_trend = max(0.0, min(100.0, float(theme.get("web_trend", 0))))
        except (TypeError, ValueError):
            web_trend = 0.0
        vol = volume_score(total_msgs)
        sent = sentiment_score(bullish, bearish)
        mom = momentum_score(sum(returns) / len(returns) if returns else 0.0)
        hotness = weighted_hotness(
            web_trend=web_trend, community_volume=vol, sentiment=sent, momentum=mom
        )
        return TrendingSector(
            name=str(theme.get("name", "(이름 없음)")),
            description=str(theme.get("description", "")),
            keywords=[str(k) for k in (theme.get("keywords") or [])],
            tickers=tickers,
            hotness_score=round(hotness, 1),
            signals=TrendingSignals(
                web_trend=round(web_trend, 1),
                community_volume=round(vol, 1),
                sentiment=round(sent, 1),
                momentum=round(mom, 1),
            ),
            rationale=_rationale(web_trend, vol, sent, mom),
        )


class FakeTrendingFinder:
    """Token-free finder for WEB_FAKE_RUNNER / E2E. Emits same stage events.

    Args:
        bus: EventBus to publish stage-progress events to.
    """

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus

    async def find(self, job_id: str) -> list[TrendingSector]:
        """Emit the four stage events then return deterministic dummy themes.

        Args:
            job_id: EventBus run-id to publish progress under.

        Returns:
            Three dummy themes sorted by hotness descending.
        """
        for stage in ("discover", "enrich", "score", "rank"):
            _progress(self.bus, job_id, stage, message=f"{stage}…")
            # Small delay so the UI can render each stage transition during E2E.
            await asyncio.sleep(0.01)
        # Hand-picked dummy values (hotness not recomputed from signals) — this
        # finder only exercises the SSE/UI path under WEB_FAKE_RUNNER.
        dummy = [
            ("온디바이스 AI", 82.0, 80, 75, 85, 70, ["AAPL", "QCOM"]),
            ("원전 SMR", 71.0, 75, 60, 70, 65, ["SMR", "CCJ"]),
            ("우주 발사체", 64.0, 70, 55, 60, 55, ["RKLB", "ASTR"]),
        ]
        out = [
            TrendingSector(
                name=n,
                description=f"{n} 관련 테마(더미)",
                keywords=[n],
                tickers=tks,
                hotness_score=score,
                signals=TrendingSignals(
                    web_trend=wt, community_volume=cv, sentiment=se, momentum=mo
                ),
                rationale="WEB_FAKE_RUNNER 더미 결과",
            )
            for (n, score, wt, cv, se, mo, tks) in dummy
        ]
        return out
