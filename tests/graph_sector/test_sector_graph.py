import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from tradingagents.graph_sector.sector_graph import build_sector_graph
from tradingagents.graph_sector.state import SectorState


def test_graph_runs_all_four_phases():
    deep = MagicMock()
    deep.bind_tools.return_value = deep
    deep.invoke.side_effect = [
        AIMessage(content="# Macro"),  # macro
        AIMessage(content=json.dumps({  # value_chain
            "stages": [{"name": "U", "description": "", "key_companies": []}],
            "mermaid": "graph LR\n  U[U]"
        })),
        AIMessage(content=json.dumps({  # competitive
            "companies": [
                {"name": "X", "stage": "U", "share_value": 50.0,
                 "share_basis": "reported", "confidence": "high", "sources": []}
            ]
        })),
        AIMessage(content=json.dumps({  # outlook
            "summary_md": "## OK",
            "candidate_tickers": [
                {"ticker": "X", "name": "X", "stage": "U", "reason": "lead"}
            ]
        })),
    ]
    graph = build_sector_graph(quick_llm=deep, deep_llm=deep)
    state = SectorState.from_request(
        sector_slug="ai", sector_name="AI", keywords=["GPU"]
    )
    final = graph.invoke(state)
    assert final["macro_report"].startswith("# Macro")
    assert final["value_chain_mermaid"].startswith("graph LR")
    assert len(final["companies"]) == 1
    assert final["candidate_tickers"][0]["ticker"] == "X"
