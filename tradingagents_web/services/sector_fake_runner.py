"""Fake sector runner — for WEB_FAKE_RUNNER=true UI/E2E/SSE testing.

Emits the same phase-progress event shape as a real run but skips the LLM
and Tavily calls. Use this to validate the full backend → SSE → frontend
flow without spending tokens or hitting external APIs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from tradingagents_web.services.event_bus import AnalysisEvent, EventBus

SECTOR_PHASE_ORDER: tuple[str, ...] = (
    "macro",
    "value_chain",
    "competitive",
    "outlook",
)
SECTOR_PHASE_LABELS: dict[str, str] = {
    "macro": "거시 환경",
    "value_chain": "가치사슬",
    "competitive": "경쟁 구도",
    "outlook": "투자 전망",
}
SECTOR_PHASE_TOTAL: int = len(SECTOR_PHASE_ORDER)


def sector_progress_payload(phase: str) -> dict[str, Any]:
    """Build the SSE ``progress`` event payload for a sector phase transition.

    Args:
        phase: Phase key (must be in :data:`SECTOR_PHASE_ORDER`).

    Returns:
        Payload dict with ``step``/``total`` (for the UI gauge) plus
        ``phase``/``phase_label`` for the phase-based progress display.
    """
    return {
        "step": SECTOR_PHASE_ORDER.index(phase) + 1,
        "total": SECTOR_PHASE_TOTAL,
        "phase": phase,
        "phase_label": SECTOR_PHASE_LABELS[phase],
    }


@dataclass
class SectorRunRequest:
    """Request payload describing a single sector analysis run.

    Attributes:
        run_id: Unique identifier for this run (UUID string).
        sector_id: Database primary key of the target sector row.
        sector_slug: URL-friendly sector identifier (e.g. ``"ai"``).
        sector_name: Human-readable sector name shown to the user.
        keywords: Optional keywords passed to the LLM/search prompts.
        analysis_date: The date the analysis is anchored to.
        llm_quick_model: Optional model ID for quick-think operations.
        llm_deep_model: Optional model ID for deep-think operations.
    """

    run_id: str
    sector_id: int
    sector_slug: str
    sector_name: str
    keywords: list[str]
    analysis_date: date
    llm_quick_model: str | None = None
    llm_deep_model: str | None = None


@dataclass
class SectorRunResult:
    """Result returned by a sector runner once the graph completes.

    Attributes:
        report_md: Final markdown report text rendered for the user.
        value_chain_mermaid: Mermaid ``graph LR`` source for the value chain.
        companies: List of company dicts with stage/share metadata.
        outlook_summary: Markdown summary of opportunities and risks.
        candidate_tickers: List of recommended tickers with rationale.
        search_call_count: Number of external search calls used (0 for fake).
    """

    report_md: str
    value_chain_mermaid: str
    companies: list[dict[str, Any]] = field(default_factory=list)
    outlook_summary: str = ""
    candidate_tickers: list[dict[str, Any]] = field(default_factory=list)
    search_call_count: int = 0


_DUMMY_MERMAID = """graph LR
  U[Upstream — 소재/장비] --> M[Midstream — 제조]
  M --> D[Downstream — 최종 제품]
"""

_DUMMY_COMPANIES: list[dict[str, Any]] = [
    {
        "name": "ASML",
        "ticker": "ASML",
        "stage": "Upstream — EUV 노광장비",
        "share_value": 65.0,
        "share_basis": "reported",
        "confidence": "high",
        "sources": ["https://www.asml.com/en/investors"],
    },
    {
        "name": "TSMC",
        "ticker": "TSM",
        "stage": "Midstream — 파운드리",
        "share_value": 55.0,
        "share_basis": "reported",
        "confidence": "high",
        "sources": ["https://example.com/tsm"],
    },
]

_DUMMY_CANDIDATES: list[dict[str, Any]] = [
    {
        "ticker": "NVDA",
        "name": "NVIDIA",
        "stage": "Downstream — AI 가속기",
        "reason": "AI 가속기 시장 점유율 80% 이상",
    },
    {
        "ticker": "TSM",
        "name": "TSMC",
        "stage": "Midstream — 파운드리",
        "reason": "선단공정 사실상 독점",
    },
]


class FakeSectorRunner:
    """Drop-in sector runner that emits scripted events with no LLM cost.

    Mirrors the event sequence of a real sector run (4 phase progress events
    followed by a terminal ``done`` event) so the UI / SSE pipeline can be
    exercised end-to-end without invoking the actual LangGraph or Tavily.

    Args:
        bus: The :class:`EventBus` to publish events to.

    Example:
        >>> bus = EventBus()
        >>> runner = FakeSectorRunner(bus=bus)
        >>> result = await runner.run(req)
        >>> assert result.report_md.startswith("#")
    """

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus

    async def run(self, request: SectorRunRequest) -> SectorRunResult:
        """Run the fake sector analysis and emit deterministic events.

        Emits one ``progress`` event per phase in :data:`SECTOR_PHASE_ORDER`,
        followed by a single ``done`` event carrying the ``sector_id``.
        Always calls :meth:`EventBus.finish` so subscribers terminate cleanly.

        Args:
            request: The :class:`SectorRunRequest` (only ``run_id``,
                ``sector_id`` and ``sector_name`` are used by the fake).

        Returns:
            A :class:`SectorRunResult` populated with dummy report content.
        """
        for phase in SECTOR_PHASE_ORDER:
            self.bus.publish(
                request.run_id,
                AnalysisEvent(type="progress", data=sector_progress_payload(phase)),
            )
            # Brief sleep so the UI can show each phase transition.
            await asyncio.sleep(0.01)

        result = SectorRunResult(
            report_md=(
                f"# {request.sector_name} 산업 분석\n\n"
                "(WEB_FAKE_RUNNER=true 모드의 더미 리포트)\n"
            ),
            value_chain_mermaid=_DUMMY_MERMAID,
            companies=_DUMMY_COMPANIES,
            outlook_summary=(
                "## 수혜\n선단공정 의존도가 높아 파운드리·장비 업체에 유리.\n"
                "## 리스크\n중국 규제와 수출 통제 변동.\n"
            ),
            candidate_tickers=_DUMMY_CANDIDATES,
            search_call_count=0,
        )
        self.bus.publish(
            request.run_id,
            AnalysisEvent(type="done", data={"sector_id": request.sector_id}),
        )
        self.bus.finish(request.run_id)
        return result
