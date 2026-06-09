"""Real sector runner — drives the sector LangGraph and emits phase progress.

Mirrors ``tradingagents_web.services.runner.RealRunner`` for the
``graph_sector`` package. Phase mapping collapses LangGraph node names to
four user-facing phases (macro / value_chain / competitive / outlook).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from tradingagents.graph_sector.sector_graph import build_sector_graph
from tradingagents.graph_sector.state import SectorState

# SearchBudget is constructed inside SectorState.from_request() — no direct
# import here. We reuse state.budget so env vars actually take effect.
from tradingagents_web.services.concurrency import analysis_slot
from tradingagents_web.services.event_bus import AnalysisEvent, EventBus
from tradingagents_web.services.sector_fake_runner import (
    SectorRunRequest,
    SectorRunResult,
    sector_progress_payload,
)

logger = logging.getLogger(__name__)

LLMFactory = Callable[[str | None], object]

_NODE_TO_PHASE: dict[str, str] = {
    "macro_overview": "macro",
    "value_chain": "value_chain",
    "competitive_landscape": "competitive",
    "investment_outlook": "outlook",
}


class RealSectorRunner:
    """Drives the sector LangGraph and emits AnalysisEvents on phase changes.

    NOTE on budget lifetime: a fresh ``SearchBudget`` and a freshly
    compiled graph are created INSIDE every ``run()`` call. Reusing the
    same graph across runs would leak budget counters via closure capture
    (see node factory docstrings).
    """

    def __init__(self, bus: EventBus, *, llm_factory: LLMFactory) -> None:
        self.bus = bus
        self.llm_factory = llm_factory

    async def run(self, request: SectorRunRequest) -> SectorRunResult:
        """Stream the sector graph and emit phase-progress events.

        Args:
            request: Fully populated :class:`SectorRunRequest`.

        Returns:
            A :class:`SectorRunResult` assembled from the final graph state.

        Raises:
            Exception: Re-raises any exception after publishing an ``error``
                event and finishing the bus for this run.
        """
        # Per-run isolation: new LLMs, new budget, new compiled graph.
        # Caching any of these at module/instance scope would leak the
        # SearchBudget counter across runs via node closure capture.
        deep_llm = self.llm_factory(request.llm_deep_model)
        quick_llm = self.llm_factory(request.llm_quick_model)
        # Build state FIRST so its env-driven budget (SECTOR_SEARCH_BUDGET /
        # SECTOR_NODE_SEARCH_BUDGET) is what actually gates web_search calls.
        # Reuse the same budget object in the graph closures — otherwise the
        # node closures would cap at the SearchBudget() default (12/3) and
        # ignore operator overrides.
        state = SectorState.from_request(
            sector_slug=request.sector_slug,
            sector_name=request.sector_name,
            keywords=request.keywords,
        )
        budget = state.budget
        graph = build_sector_graph(
            quick_llm=quick_llm, deep_llm=deep_llm, budget=budget,
        )

        seen_phases: set[str] = set()
        final_state: dict[str, Any] | None = None

        try:
            # Cap concurrent graph runs so sector fan-out + parallel runs cannot
            # exhaust the per-process fd limit (see services.concurrency).
            async with analysis_slot():
                async for chunk in graph.astream(state):
                    # chunk format: {node_name: state_partial}
                    for node_name, partial in chunk.items():
                        phase = _NODE_TO_PHASE.get(node_name)
                        if phase and phase not in seen_phases:
                            seen_phases.add(phase)
                            self.bus.publish(
                                request.run_id,
                                AnalysisEvent(
                                    type="progress",
                                    data=sector_progress_payload(phase),
                                ),
                            )
                        if partial:
                            final_state = {**(final_state or {}), **partial}
        except Exception as exc:
            logger.exception("sector_runner: graph failed")
            self.bus.publish(
                request.run_id,
                AnalysisEvent(type="error", data={"message": str(exc)}),
            )
            self.bus.finish(request.run_id)
            raise

        if final_state is None:
            self.bus.publish(
                request.run_id,
                AnalysisEvent(
                    type="error", data={"message": "graph produced no state"}
                ),
            )
            self.bus.finish(request.run_id)
            raise RuntimeError("graph produced no state")

        report_md = self._compose_report_md(request.sector_name, final_state)
        result = SectorRunResult(
            report_md=report_md,
            value_chain_mermaid=final_state.get("value_chain_mermaid", ""),
            companies=final_state.get("companies", []),
            outlook_summary=final_state.get("outlook_md", ""),
            candidate_tickers=final_state.get("candidate_tickers", []),
            search_call_count=budget.total_used,
        )
        # NOTE: emitting `done` + `bus.finish()` is the caller's responsibility
        # (api/sectors._execute_sector_run). The caller commits the SectorReport
        # row first, then signals completion — otherwise an SSE client reacting
        # to `done` could race to GET /reports/latest before the row is visible.
        return result

    @staticmethod
    def _compose_report_md(sector_name: str, state: dict[str, Any]) -> str:
        """Stitch the per-node outputs into a single user-facing markdown report."""
        parts: list[str] = [
            f"# {sector_name} 산업 분석",
            f"_생성: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_",
            "## 거시 환경",
            state.get("macro_report") or "_데이터 없음_",
            state.get("value_chain_md") or "## 가치사슬\n_데이터 없음_",
            "## 경쟁 구도 · 핵심 기업",
            _companies_md_table(state.get("companies", [])),
            "## 투자 전망",
            state.get("outlook_md") or "_데이터 없음_",
        ]
        return "\n\n".join(p for p in parts if p is not None)


def _companies_md_table(companies: list[dict[str, Any]]) -> str:
    """Render the structured companies list as a markdown table."""
    if not companies:
        return "_데이터 없음_"
    rows = ["| 기업 | 단계 | 점유율 | 근거 | 신뢰도 |", "|---|---|---|---|---|"]
    for c in companies:
        ticker = c.get("ticker") or "-"
        rows.append(
            f"| {c['name']} ({ticker}) | {c['stage']} "
            f"| {c['share_value']}% | {c['share_basis']} | {c['confidence']} |"
        )
    return "\n".join(rows)
