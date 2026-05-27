from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.nodes.macro_overview import make_macro_overview_node
from tradingagents.graph_sector.state import SectorState


def test_macro_overview_writes_report_md():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content="# Macro\n시장 규모 X조원")

    node = make_macro_overview_node(llm, budget=None)
    state = SectorState(sector_slug="ai", sector_name="AI", keywords=["GPU"])
    result = node(state)
    assert "macro_report" in result
    assert "시장 규모" in result["macro_report"]
