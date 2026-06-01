import unittest
from unittest.mock import MagicMock

from tradingagents.agents.analysts.social_media_analyst import create_social_media_analyst


class SocialAnalystWiringTests(unittest.TestCase):
    def setUp(self):
        self.captured_tools = None
        self.captured_messages = None

        class FakeChain:
            def __init__(self, outer):
                self.outer = outer

            def invoke(self, messages):
                self.outer.captured_messages = messages
                result = MagicMock()
                result.tool_calls = []
                result.content = "REPORT"
                return result

        outer = self

        class FakeLLM:
            def bind_tools(self, tools):
                outer.captured_tools = tools
                return MagicMock()

        # Build the chain manually so we can intercept .invoke
        fake_llm = FakeLLM()
        # Patch the prompt-piping by replacing chain construction in the node.
        # Easiest: just use the real node and assert on bound tools.
        self._fake_llm = fake_llm

    def test_node_binds_only_social_tools(self):
        # We can detect binding by replacing bind_tools in a real LLM stub.
        node = create_social_media_analyst(self._fake_llm)
        try:
            node({
                "trade_date": "2026-05-08",
                "company_of_interest": "AAPL",
                "messages": [],
            })
        except Exception:
            # Downstream call into a MagicMock chain will fail; we only need
            # bind_tools to have been called by then.
            pass

        self.assertIsNotNone(self.captured_tools)
        names = sorted(t.name for t in self.captured_tools)
        self.assertEqual(names, ["get_social_messages", "get_social_sentiment"])

    def test_system_prompt_contains_correct_signatures(self):
        # Inspect the source to verify the analyst's prompt advertises the
        # exact tool signatures and the bare-ticker guard string.
        import inspect
        from tradingagents.agents.analysts import social_media_analyst as mod

        src = inspect.getsource(mod)
        self.assertIn("get_social_sentiment(ticker, start_date, end_date)", src)
        self.assertIn("get_social_messages(ticker, limit, sort, days)", src)
        self.assertIn("bare ticker symbol", src)


if __name__ == "__main__":
    unittest.main()
