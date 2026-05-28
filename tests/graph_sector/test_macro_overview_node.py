from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.nodes.macro_overview import make_macro_overview_node
from tradingagents.graph_sector.state import SectorState
from tradingagents.graph_sector.tools.web_search import SearchBudget


def test_macro_overview_writes_report_md():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content="# Macro\n시장 규모 X조원")

    node = make_macro_overview_node(llm, budget=None)
    state = SectorState(sector_slug="ai", sector_name="AI", keywords=["GPU"])
    result = node(state)
    assert "macro_report" in result
    assert "시장 규모" in result["macro_report"]


def test_macro_overview_executes_tool_calls():
    """If the model requests web_search, the loop must execute the tool and
    feed the result back to the model before returning the final report.

    The plan flagged this as a structural defect: bind_tools() only lets the
    model REQUEST tools — it does not execute them. invoke_with_tool_loop()
    closes that gap.
    """
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    # 1st turn: AI requests web_search.
    # 2nd turn: AI returns the real report.
    llm.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "web_search",
                "args": {"query": "AI accelerator market 2026"},
                "id": "call-1",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="# Macro\n시장 규모: USD 200B (2024 기준)"),
    ]
    fake_client = MagicMock()
    fake_client.search.return_value = {"results": [
        {"title": "X", "url": "https://x.com", "content": "snippet"},
    ]}
    budget = SearchBudget(total=5, per_node=3)
    with patch(
        "tradingagents.graph_sector.tools.web_search.TavilyClient",
        return_value=fake_client,
    ):
        node = make_macro_overview_node(llm, budget=budget)
        state = SectorState(sector_slug="ai", sector_name="AI", keywords=["GPU"])
        result = node(state)
    assert "시장 규모" in result["macro_report"]
    assert llm.invoke.call_count == 2
    # The tool was actually invoked → budget charged
    assert budget.total_used == 1


def test_macro_overview_swallows_malformed_tool_call():
    """Model emits a tool_call with invalid args — the loop must NOT crash.

    langchain @tool wraps args in a Pydantic schema; missing required fields
    like 'query' make tool.invoke({}) raise ValidationError. Without the
    try/except in _tool_loop the whole sector analysis would die.
    """
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "web_search",
                "args": {},  # missing 'query' — will raise
                "id": "call-1",
                "type": "tool_call",
            }],
        ),
        AIMessage(content="# Macro\n시장 규모: USD 200B"),
    ]
    budget = SearchBudget(total=5, per_node=3)
    node = make_macro_overview_node(llm, budget=budget)
    state = SectorState(sector_slug="ai", sector_name="AI", keywords=[])
    result = node(state)  # must NOT raise
    assert "시장 규모" in result["macro_report"]
    # Bad tool_call → no Tavily round-trip → budget untouched
    assert budget.total_used == 0
