import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.nodes.investment_outlook import (
    make_investment_outlook_node,
)
from tradingagents.graph_sector.state import SectorState

_VALID = {
    "summary_md": "## 전망\n수혜: ...\n리스크: ...",
    "candidate_tickers": [
        {"ticker": "NVDA", "name": "NVIDIA", "stage": "Downstream", "reason": "AI accelerator leader"},
        {"ticker": "TSM", "name": "TSMC", "stage": "Midstream", "reason": "foundry"},
    ]
}


def test_outlook_fields_populated():
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content=json.dumps(_VALID))
    node = make_investment_outlook_node(llm)
    state = SectorState(sector_slug="x", sector_name="X", keywords=[])
    state.companies = [{"name": "NVIDIA", "ticker": "NVDA", "stage": "Downstream",
                        "share_value": 80, "share_basis": "reported",
                        "confidence": "high", "sources": []}]
    result = node(state)
    assert "수혜" in result["outlook_md"]
    assert len(result["candidate_tickers"]) == 2
    assert result["candidate_tickers"][0]["ticker"] == "NVDA"


def test_outlook_fallback_on_invalid_json():
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content="not json")
    node = make_investment_outlook_node(llm)
    result = node(SectorState(sector_slug="x", sector_name="X", keywords=[]))
    assert result["candidate_tickers"] == []
    assert result["outlook_md"] == "not json"
