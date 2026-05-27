"""SectorState — LangGraph state for the sector analysis graph."""
from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from tradingagents.graph_sector.tools.web_search import SearchBudget


@dataclass
class SectorState:
    """LangGraph state passed between sector analysis nodes."""

    sector_slug: str
    sector_name: str
    keywords: list[str]
    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    macro_report: str = ""
    value_chain_md: str = ""
    value_chain_mermaid: str = ""
    companies: list[dict[str, Any]] = field(default_factory=list)
    outlook_md: str = ""
    candidate_tickers: list[dict[str, Any]] = field(default_factory=list)
    budget: SearchBudget = field(default_factory=SearchBudget)

    @classmethod
    def from_request(
        cls,
        *,
        sector_slug: str,
        sector_name: str,
        keywords: list[str],
    ) -> SectorState:
        """Build a SectorState with budgets sourced from environment variables.

        Reads ``SECTOR_SEARCH_BUDGET`` (total) and ``SECTOR_NODE_SEARCH_BUDGET``
        (per-node), falling back to ``SearchBudget`` defaults (12 / 3) when
        unset. Use this entry point when starting a new graph run; direct
        ``SectorState(...)`` construction is fine for tests that don't care
        about env overrides.
        """
        total = int(os.environ.get("SECTOR_SEARCH_BUDGET", "12"))
        per_node = int(os.environ.get("SECTOR_NODE_SEARCH_BUDGET", "3"))
        return cls(
            sector_slug=sector_slug,
            sector_name=sector_name,
            keywords=keywords,
            budget=SearchBudget(total=total, per_node=per_node),
        )
