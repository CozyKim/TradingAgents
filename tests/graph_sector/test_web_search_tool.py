from unittest.mock import MagicMock, patch

from tradingagents.graph_sector.tools.web_search import (
    SearchBudget,
    make_web_search_tool,
)


def test_budget_exhausted_returns_empty():
    budget = SearchBudget(total=2, per_node=3)
    tool = make_web_search_tool(budget)
    budget.total_used = 2
    result = tool.invoke({"query": "anything"})
    assert result == []


def test_per_node_budget_exhausted_returns_empty():
    budget = SearchBudget(total=10, per_node=1, current_node="macro")
    tool = make_web_search_tool(budget)
    budget.per_node_used["macro"] = 1
    result = tool.invoke({"query": "anything"})
    assert result == []


def test_successful_call_returns_normalized_results():
    fake_client = MagicMock()
    fake_client.search.return_value = {
        "results": [
            {"title": "T", "url": "https://example.com", "content": "snippet"},
        ]
    }
    budget = SearchBudget(total=10, per_node=3, current_node="macro")
    with patch(
        "tradingagents.graph_sector.tools.web_search.TavilyClient",
        return_value=fake_client,
    ):
        tool = make_web_search_tool(budget)
        result = tool.invoke({"query": "AI market"})
    assert result == [{"title": "T", "url": "https://example.com", "snippet": "snippet"}]
    assert budget.total_used == 1
    assert budget.per_node_used["macro"] == 1


def test_failed_call_still_charges_budget():
    """Tavily errors after construction (rate-limits, timeouts) must count.

    Otherwise a ReAct loop could burn unbounded retries against the same node.
    """
    fake_client = MagicMock()
    fake_client.search.side_effect = RuntimeError("HTTP 429 too many requests")
    budget = SearchBudget(total=10, per_node=3, current_node="macro")
    with patch(
        "tradingagents.graph_sector.tools.web_search.TavilyClient",
        return_value=fake_client,
    ):
        tool = make_web_search_tool(budget)
        result = tool.invoke({"query": "AI market"})
    assert result == []
    assert budget.total_used == 1
    assert budget.per_node_used["macro"] == 1
