import unittest
from unittest.mock import MagicMock, patch

from tradingagents.dataflows import interface


class SocialRoutingTests(unittest.TestCase):
    def test_social_data_category_registered(self):
        self.assertIn("social_data", interface.TOOLS_CATEGORIES)
        tools = interface.TOOLS_CATEGORIES["social_data"]["tools"]
        self.assertIn("get_social_sentiment", tools)
        self.assertIn("get_social_messages", tools)

    def test_get_social_sentiment_routes_to_finnhub(self):
        # VENDOR_METHODS holds direct function references, so we replace the
        # registered finnhub impl for the duration of this test.
        original = interface.VENDOR_METHODS["get_social_sentiment"]["finnhub"]
        mock_fn = MagicMock(return_value="FINNHUB_OK")
        interface.VENDOR_METHODS["get_social_sentiment"]["finnhub"] = mock_fn
        try:
            out = interface.route_to_vendor(
                "get_social_sentiment", "AAPL", "2026-05-01", "2026-05-08"
            )
        finally:
            interface.VENDOR_METHODS["get_social_sentiment"]["finnhub"] = original

        self.assertEqual(out, "FINNHUB_OK")
        mock_fn.assert_called_once_with("AAPL", "2026-05-01", "2026-05-08")

    def test_get_social_messages_routes_to_stocktwits(self):
        original = interface.VENDOR_METHODS["get_social_messages"]["stocktwits"]
        mock_fn = MagicMock(return_value="ST_OK")
        interface.VENDOR_METHODS["get_social_messages"]["stocktwits"] = mock_fn
        try:
            out = interface.route_to_vendor("get_social_messages", "AAPL", 30)
        finally:
            interface.VENDOR_METHODS["get_social_messages"]["stocktwits"] = original

        self.assertEqual(out, "ST_OK")
        mock_fn.assert_called_once_with("AAPL", 30)

    def test_get_category_for_social_methods(self):
        self.assertEqual(
            interface.get_category_for_method("get_social_sentiment"), "social_data"
        )
        self.assertEqual(
            interface.get_category_for_method("get_social_messages"), "social_data"
        )


class SocialToolWrapperTests(unittest.TestCase):
    def test_get_social_sentiment_tool_invokes_router(self):
        from tradingagents.agents.utils.social_data_tools import get_social_sentiment

        with patch(
            "tradingagents.agents.utils.social_data_tools.route_to_vendor",
            return_value="ROUTED",
        ) as mock_route:
            result = get_social_sentiment.invoke(
                {"ticker": "AAPL", "start_date": "2026-05-01", "end_date": "2026-05-08"}
            )
            self.assertEqual(result, "ROUTED")
            mock_route.assert_called_once_with(
                "get_social_sentiment", "AAPL", "2026-05-01", "2026-05-08"
            )

    def test_get_social_messages_tool_invokes_router(self):
        from tradingagents.agents.utils.social_data_tools import get_social_messages

        with patch(
            "tradingagents.agents.utils.social_data_tools.route_to_vendor",
            return_value="ROUTED",
        ) as mock_route:
            result = get_social_messages.invoke({"ticker": "AAPL", "limit": 25})
            self.assertEqual(result, "ROUTED")
            mock_route.assert_called_once_with("get_social_messages", "AAPL", 25)


if __name__ == "__main__":
    unittest.main()
