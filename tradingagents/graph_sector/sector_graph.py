"""LangGraph builder for the 4-stage sector analysis graph."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from tradingagents.graph_sector.nodes.competitive_landscape import (
    make_competitive_node,
)
from tradingagents.graph_sector.nodes.investment_outlook import (
    make_investment_outlook_node,
)
from tradingagents.graph_sector.nodes.macro_overview import make_macro_overview_node
from tradingagents.graph_sector.nodes.value_chain import make_value_chain_node
from tradingagents.graph_sector.state import SectorState
from tradingagents.graph_sector.tools.web_search import SearchBudget


def build_sector_graph(*, quick_llm, deep_llm, budget: SearchBudget | None = None):
    """Compile a sequential 4-stage StateGraph.

    Macro → ValueChain → Competitive → Outlook → END.

    NOTE on budget lifetime: ``budget`` is captured into the macro/
    value_chain/competitive node closures. Callers MUST call
    ``build_sector_graph`` (with a fresh ``SearchBudget``) for every
    analysis run; reusing a single compiled graph across runs would leak
    search counts. RealSectorRunner (Task 13) does this — it calls
    build_sector_graph inside each run().

    Args:
        quick_llm: Currently unused. Reserved for nodes that need a
            cheaper/faster model for short tasks (e.g. confidence judging
            in the broader runner). Kept in the signature for parity with
            ``tradingagents.graph.trading_graph`` and to leave room for
            future optimization without breaking callers.
        deep_llm: The model used by all four sector nodes today.
        budget: Per-run search budget. When None, nodes still run but
            cannot call ``web_search``.
    """
    g = StateGraph(SectorState)
    g.add_node("macro_overview", make_macro_overview_node(deep_llm, budget))
    g.add_node("value_chain", make_value_chain_node(deep_llm, budget))
    g.add_node("competitive_landscape", make_competitive_node(deep_llm, budget))
    g.add_node("investment_outlook", make_investment_outlook_node(deep_llm))

    g.set_entry_point("macro_overview")
    g.add_edge("macro_overview", "value_chain")
    g.add_edge("value_chain", "competitive_landscape")
    g.add_edge("competitive_landscape", "investment_outlook")
    g.add_edge("investment_outlook", END)
    return g.compile()
