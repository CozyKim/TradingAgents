import unittest
from unittest.mock import patch, MagicMock

from tradingagents.dataflows import finnhub_social
from tradingagents.dataflows.finnhub_common import (
    FinnhubAuthError,
    FinnhubRateLimitError,
)


def _mock_response(status_code: int, json_data: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = "" if json_data is None else str(json_data)
    return resp


class GetSocialSentimentFinnhubTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_key_returns_explicit_message(self):
        result = finnhub_social.get_social_sentiment_finnhub("AAPL", "2026-05-01", "2026-05-08")
        self.assertIn("FINNHUB_API_KEY not set", result)

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_success_renders_markdown_table(self, mock_get):
        payload = {
            "symbol": "AAPL",
            "reddit": [
                {"atTime": "2026-05-02 00:00:00", "mention": 12, "positiveScore": 0.7,
                 "negativeScore": 0.1, "score": 0.6},
            ],
            "twitter": [
                {"atTime": "2026-05-02 00:00:00", "mention": 30, "positiveScore": 0.5,
                 "negativeScore": 0.2, "score": 0.3},
            ],
        }
        mock_get.return_value = _mock_response(200, payload)
        result = finnhub_social.get_social_sentiment_finnhub("AAPL", "2026-05-01", "2026-05-08")
        self.assertIn("AAPL", result)
        self.assertIn("Reddit", result)
        self.assertIn("Twitter", result)
        self.assertIn("12", result)
        self.assertIn("30", result)

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_empty_payload_returns_no_data_message(self, mock_get):
        mock_get.return_value = _mock_response(200, {"symbol": "AAPL", "reddit": [], "twitter": []})
        result = finnhub_social.get_social_sentiment_finnhub("AAPL", "2026-05-01", "2026-05-08")
        self.assertIn("No social sentiment data", result)
        self.assertIn("AAPL", result)

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_401_raises_auth_error(self, mock_get):
        mock_get.return_value = _mock_response(401, {"error": "Invalid API key"})
        with self.assertRaises(FinnhubAuthError):
            finnhub_social.get_social_sentiment_finnhub("AAPL", "2026-05-01", "2026-05-08")

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_429_raises_rate_limit_error(self, mock_get):
        mock_get.return_value = _mock_response(429, {"error": "rate limit"})
        with self.assertRaises(FinnhubRateLimitError):
            finnhub_social.get_social_sentiment_finnhub("AAPL", "2026-05-01", "2026-05-08")

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_network_error_returns_friendly_message(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("boom")
        result = finnhub_social.get_social_sentiment_finnhub("AAPL", "2026-05-01", "2026-05-08")
        self.assertIn("Error fetching social sentiment", result)
        self.assertIn("AAPL", result)


if __name__ == "__main__":
    unittest.main()
