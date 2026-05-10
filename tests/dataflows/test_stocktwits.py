import unittest
from unittest.mock import patch, MagicMock

from tradingagents.dataflows import stocktwits


def _mock_response(status_code: int, json_data: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


class GetSocialMessagesStocktwitsTests(unittest.TestCase):
    @patch("tradingagents.dataflows.stocktwits.requests.get")
    def test_success_renders_messages(self, mock_get):
        payload = {
            "messages": [
                {
                    "body": "AAPL looking strong",
                    "created_at": "2026-05-08T12:34:56Z",
                    "user": {"username": "alice"},
                    "entities": {"sentiment": {"basic": "Bullish"}},
                },
                {
                    "body": "Not convinced",
                    "created_at": "2026-05-08T12:00:00Z",
                    "user": {"username": "bob"},
                    "entities": {"sentiment": None},
                },
            ]
        }
        mock_get.return_value = _mock_response(200, payload)
        result = stocktwits.get_social_messages_stocktwits("AAPL", 30)
        self.assertIn("alice", result)
        self.assertIn("Bullish", result)
        self.assertIn("AAPL looking strong", result)
        self.assertIn("bob", result)
        self.assertIn("None", result)

    @patch("tradingagents.dataflows.stocktwits.requests.get")
    def test_empty_messages(self, mock_get):
        mock_get.return_value = _mock_response(200, {"messages": []})
        result = stocktwits.get_social_messages_stocktwits("AAPL", 30)
        self.assertIn("No StockTwits messages found", result)

    @patch("tradingagents.dataflows.stocktwits.requests.get")
    def test_404_returns_no_stream_message(self, mock_get):
        mock_get.return_value = _mock_response(404, {"errors": [{"message": "Not Found"}]})
        result = stocktwits.get_social_messages_stocktwits("FAKE", 30)
        self.assertIn("No StockTwits stream found", result)

    @patch("tradingagents.dataflows.stocktwits.requests.get")
    def test_429_returns_rate_limit_message(self, mock_get):
        mock_get.return_value = _mock_response(429, {})
        result = stocktwits.get_social_messages_stocktwits("AAPL", 30)
        self.assertIn("rate-limited", result)

    @patch("tradingagents.dataflows.stocktwits.requests.get")
    def test_403_returns_blocked_message(self, mock_get):
        mock_get.return_value = _mock_response(403, {})
        result = stocktwits.get_social_messages_stocktwits("AAPL", 30)
        self.assertIn("403", result)
        self.assertIn("blocked", result)

    @patch("tradingagents.dataflows.stocktwits.requests.get")
    def test_request_sends_browser_user_agent(self, mock_get):
        mock_get.return_value = _mock_response(200, {"messages": []})
        stocktwits.get_social_messages_stocktwits("AAPL", 30)
        headers = mock_get.call_args.kwargs.get("headers") or {}
        self.assertIn("User-Agent", headers)
        self.assertIn("Mozilla", headers["User-Agent"])

    @patch("tradingagents.dataflows.stocktwits.requests.get")
    def test_limit_clamping_low(self, mock_get):
        mock_get.return_value = _mock_response(200, {"messages": []})
        stocktwits.get_social_messages_stocktwits("AAPL", 0)
        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(called_params["limit"], 1)

    @patch("tradingagents.dataflows.stocktwits.requests.get")
    def test_limit_clamping_high(self, mock_get):
        mock_get.return_value = _mock_response(200, {"messages": []})
        stocktwits.get_social_messages_stocktwits("AAPL", 999)
        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(called_params["limit"], 50)

    @patch("tradingagents.dataflows.stocktwits.requests.get")
    def test_body_truncation(self, mock_get):
        long_body = "x" * 500
        payload = {"messages": [{
            "body": long_body, "created_at": "2026-05-08T00:00:00Z",
            "user": {"username": "u"}, "entities": {"sentiment": None},
        }]}
        mock_get.return_value = _mock_response(200, payload)
        result = stocktwits.get_social_messages_stocktwits("AAPL", 30)
        self.assertNotIn("x" * 500, result)
        self.assertIn("…", result)

    @patch("tradingagents.dataflows.stocktwits.requests.get")
    def test_network_error_returns_friendly_message(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("boom")
        result = stocktwits.get_social_messages_stocktwits("AAPL", 30)
        self.assertIn("Error fetching StockTwits", result)


if __name__ == "__main__":
    unittest.main()
