"""Web search tool for sector graph nodes with budget guards.

Wraps the Tavily API in a langchain ``@tool`` callable. Each invocation is
checked against (1) a per-node call budget and (2) an overall graph budget;
exceeding either limit causes the tool to return an empty list rather than
hit the API. Callers feed the budget object through closure capture so the
LangGraph ReAct loop can't bypass it.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from langchain_core.tools import tool
from tavily import TavilyClient

logger = logging.getLogger(__name__)


@dataclass
class SearchBudget:
    """Mutable budget counter shared by every web_search invocation in a run."""

    total: int = 12
    per_node: int = 3
    total_used: int = 0
    per_node_used: dict[str, int] = field(default_factory=dict)
    current_node: str | None = None

    def remaining(self) -> int:
        return max(0, self.total - self.total_used)

    def node_remaining(self) -> int:
        if not self.current_node:
            return self.per_node
        return max(0, self.per_node - self.per_node_used.get(self.current_node, 0))


def make_web_search_tool(budget: SearchBudget):
    """Return a langchain @tool bound to the given SearchBudget."""

    @tool
    def web_search(query: str) -> list[dict]:
        """Search the web for recent industry/market information.

        Returns a list of {title, url, snippet}. Returns an empty list when
        the search budget is exhausted, the API key is missing, or the
        underlying Tavily call fails.
        """
        if budget.total_used >= budget.total:
            logger.info(
                "web_search: total budget exhausted (%d/%d)",
                budget.total_used,
                budget.total,
            )
            return []
        if budget.current_node and budget.per_node_used.get(budget.current_node, 0) >= budget.per_node:
            logger.info("web_search: node budget exhausted for %s", budget.current_node)
            return []

        api_key = os.environ.get("TAVILY_API_KEY")
        try:
            client = TavilyClient(api_key=api_key)
            raw = client.search(query, max_results=5, search_depth="advanced")
        except Exception:  # noqa: BLE001 — never let search crash the graph
            logger.exception("web_search: tavily call failed")
            return []

        budget.total_used += 1
        if budget.current_node:
            budget.per_node_used[budget.current_node] = budget.per_node_used.get(budget.current_node, 0) + 1

        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in raw.get("results", [])
        ]

    return web_search
