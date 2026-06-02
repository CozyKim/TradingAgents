"""The analyst ToolNodes must not let a single tool error kill the run.

Defense-in-depth for the data layer: even if a tool raises an *unexpected*
exception (not one ``route_to_vendor`` already converts to a string), the
ToolNode is configured with ``handle_tool_errors=True`` so LangGraph turns the
failure into a ToolMessage the agent can read and route around, rather than
propagating it and aborting the whole stream.
"""

from __future__ import annotations

import unittest

from tradingagents.graph.trading_graph import TradingAgentsGraph


class ToolNodeErrorHandlingTests(unittest.TestCase):
    def test_all_graph_nodes_handle_tool_errors(self):
        # _create_tool_nodes does not touch ``self`` — build the real nodes the
        # graph uses without standing up an LLM-backed TradingAgentsGraph.
        nodes = TradingAgentsGraph._create_tool_nodes(object())
        self.assertEqual(
            set(nodes), {"market", "social", "news", "fundamentals"}
        )
        for name, node in nodes.items():
            # With this flag a raised tool exception becomes a ToolMessage
            # instead of bubbling up and killing graph.stream (verified against
            # langgraph ToolNode: True → handled_types=(Exception,)).
            self.assertTrue(
                node._handle_tool_errors,
                msg=f"ToolNode '{name}' must enable handle_tool_errors",
            )


if __name__ == "__main__":
    unittest.main()
