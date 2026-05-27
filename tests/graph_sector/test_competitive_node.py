import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.nodes.competitive_landscape import (
    make_competitive_node,
)
from tradingagents.graph_sector.state import SectorState

_VALID = {
    "companies": [
        {
            "name": "ASML", "ticker": "ASML", "stage": "Upstream — 노광장비",
            "share_value": 65.0, "share_basis": "reported",
            "confidence": "high", "sources": ["https://example.com/1"]
        },
        {
            "name": "Applied Materials", "ticker": "AMAT",
            "stage": "Upstream — 식각/증착",
            "share_value": 18.0, "share_basis": "estimated",
            "confidence": "medium", "sources": []
        },
    ]
}


def test_companies_parsed():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(_VALID))
    node = make_competitive_node(llm, budget=None)
    state = SectorState(sector_slug="x", sector_name="X", keywords=[])
    result = node(state)
    assert len(result["companies"]) == 2
    assert result["companies"][0]["share_basis"] == "reported"


def test_unknown_basis_fallback():
    bad = {"companies": [{"name": "X", "stage": "?", "share_value": 10.0,
                          "share_basis": "totally_wrong",
                          "confidence": "high", "sources": []}]}
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.return_value = AIMessage(content=json.dumps(bad))
    node = make_competitive_node(llm, budget=None)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert result["companies"][0]["share_basis"] == "unknown"
