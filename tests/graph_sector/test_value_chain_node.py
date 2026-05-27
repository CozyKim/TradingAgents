import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.nodes.value_chain import make_value_chain_node
from tradingagents.graph_sector.state import SectorState

_VALID = {
    "stages": [
        {"name": "Upstream", "description": "소재·장비",
         "key_companies": ["ASML", "Applied Materials"]},
        {"name": "Midstream", "description": "파운드리",
         "key_companies": ["TSMC"]},
        {"name": "Downstream", "description": "팹리스/IDM",
         "key_companies": ["NVIDIA", "AMD"]},
    ],
    "mermaid": "graph LR\n  U[Upstream] --> M[Midstream] --> D[Downstream]"
}


def test_value_chain_parses_json_and_populates_fields():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(_VALID))

    node = make_value_chain_node(llm, budget=None)
    state = SectorState(sector_slug="x", sector_name="X", keywords=[])
    result = node(state)
    assert result["value_chain_mermaid"].startswith("graph LR")
    assert "Upstream" in result["value_chain_md"]


def test_value_chain_retries_on_invalid_json():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [
        AIMessage(content="not json at all"),
        AIMessage(content=json.dumps(_VALID)),
    ]
    node = make_value_chain_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert llm.invoke.call_count == 2
    assert "Upstream" in result["value_chain_md"]


def test_value_chain_fallback_when_retry_fails():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content="garbage")
    node = make_value_chain_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    # Fallback: empty mermaid, value_chain_md preserves raw text
    assert result["value_chain_mermaid"] == ""
    assert "garbage" in result["value_chain_md"]
