import unittest
from unittest.mock import patch

from tradingagents.dataflows import interface


class SocialRoutingTests(unittest.TestCase):
    def test_social_data_category_registered(self):
        self.assertIn("social_data", interface.TOOLS_CATEGORIES)
        tools = interface.TOOLS_CATEGORIES["social_data"]["tools"]
        self.assertIn("get_social_sentiment", tools)
        self.assertIn("get_social_messages", tools)

    def test_get_social_sentiment_routes_to_finnhub(self):
        with patch.object(
            interface, "get_social_sentiment_finnhub", return_value="FINNHUB_OK"
        ) as mock_fn:
            out = interface.route_to_vendor(
                "get_social_sentiment", "AAPL", "2026-05-01", "2026-05-08"
            )
            self.assertEqual(out, "FINNHUB_OK")
            mock_fn.assert_called_once_with("AAPL", "2026-05-01", "2026-05-08")

    def test_get_social_messages_routes_to_stocktwits(self):
        with patch.object(
            interface, "get_social_messages_stocktwits", return_value="ST_OK"
        ) as mock_fn:
            out = interface.route_to_vendor("get_social_messages", "AAPL", 30)
            self.assertEqual(out, "ST_OK")
            mock_fn.assert_called_once_with("AAPL", 30)

    def test_get_category_for_social_methods(self):
        self.assertEqual(
            interface.get_category_for_method("get_social_sentiment"), "social_data"
        )
        self.assertEqual(
            interface.get_category_for_method("get_social_messages"), "social_data"
        )


if __name__ == "__main__":
    unittest.main()
