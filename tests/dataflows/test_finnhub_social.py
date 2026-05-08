import unittest
from unittest.mock import patch, MagicMock

from tradingagents.dataflows import finnhub_social
from tradingagents.dataflows.finnhub_common import (
    FinnhubAuthError,
    FinnhubRateLimitError,
)


def _mock_response(status_code: int, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = "" if json_data is None else str(json_data)
    return resp


# Two AAPL company-news items on 2026-05-08 (newer first by datetime),
# one item on 2026-05-07. /company-news returns a JSON array; finnhub_get
# wraps lists under {"items": ...}.
_FAKE_NEWS = [
    {
        "datetime": 1778198400,  # 2026-05-08 00:00:00 UTC + 12h ≈ 12:00 UTC
        "headline": "Apple unveils new chip",
        "source": "TestWire",
        "summary": "AAPL announces a new in-house chip aimed at AI workloads.",
    },
    {
        "datetime": 1778155200,  # earlier on 2026-05-08
        "headline": "Wedbush raises AAPL price target",
        "source": "TestWire",
        "summary": "Analyst lifts target citing services growth.",
    },
    {
        "datetime": 1778068800,  # 2026-05-07
        "headline": "AAPL supplier signals strong demand",
        "source": "OtherWire",
        "summary": "Foxconn reports strong April orders.",
    },
]


class GetSocialSentimentFinnhubTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_key_returns_explicit_message(self):
        result = finnhub_social.get_social_sentiment_finnhub("AAPL", "2026-05-01", "2026-05-08")
        self.assertIn("FINNHUB_API_KEY not set", result)

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_success_renders_grouped_digest(self, mock_get):
        # /company-news returns a list — finnhub_get wraps it under "items".
        mock_get.return_value = _mock_response(200, _FAKE_NEWS)
        result = finnhub_social.get_social_sentiment_finnhub(
            "AAPL", "2026-05-01", "2026-05-08"
        )
        self.assertIn("AAPL", result)
        self.assertIn("Company News", result)
        # All three headlines appear, each with its source.
        self.assertIn("Apple unveils new chip", result)
        self.assertIn("(TestWire)", result)
        self.assertIn("Wedbush raises AAPL price target", result)
        self.assertIn("AAPL supplier signals strong demand", result)
        self.assertIn("(OtherWire)", result)
        # Day headers for the two distinct dates in the fixture.
        # (We don't pin the exact YYYY-MM-DD here because timezone math on
        # the fixture timestamps could shift by a day — assert the day-header
        # markdown form instead.)
        self.assertIn("### 2026-05-0", result)

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_empty_payload_returns_no_data_message(self, mock_get):
        mock_get.return_value = _mock_response(200, [])
        result = finnhub_social.get_social_sentiment_finnhub(
            "AAPL", "2026-05-01", "2026-05-08"
        )
        self.assertIn("No company news for AAPL", result)

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_max_items_caps_output(self, mock_get):
        many = [
            {"datetime": 1778000000 + i * 60, "headline": f"H{i}", "source": "S",
             "summary": ""}
            for i in range(40)
        ]
        mock_get.return_value = _mock_response(200, many)
        result = finnhub_social.get_social_sentiment_finnhub(
            "AAPL", "2026-05-01", "2026-05-08", max_items=5
        )
        # Newest 5 (indices 39..35) are present; older ones are not.
        for i in range(35, 40):
            self.assertIn(f"H{i}", result)
        for i in range(0, 35):
            self.assertNotIn(f"**H{i}**", result)
        # Header reflects the capped vs. total count.
        self.assertIn("Top 5 of 40", result)

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_401_raises_auth_error(self, mock_get):
        mock_get.return_value = _mock_response(401, {"error": "Invalid API key"})
        with self.assertRaises(FinnhubAuthError):
            finnhub_social.get_social_sentiment_finnhub(
                "AAPL", "2026-05-01", "2026-05-08"
            )

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_403_raises_auth_error(self, mock_get):
        mock_get.return_value = _mock_response(403, {"error": "premium endpoint"})
        with self.assertRaises(FinnhubAuthError):
            finnhub_social.get_social_sentiment_finnhub(
                "AAPL", "2026-05-01", "2026-05-08"
            )

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_429_raises_rate_limit_error(self, mock_get):
        mock_get.return_value = _mock_response(429, {"error": "rate limit"})
        with self.assertRaises(FinnhubRateLimitError):
            finnhub_social.get_social_sentiment_finnhub(
                "AAPL", "2026-05-01", "2026-05-08"
            )

    @patch.dict("os.environ", {"FINNHUB_API_KEY": "k"})
    @patch("tradingagents.dataflows.finnhub_common.requests.get")
    def test_network_error_returns_friendly_message(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("boom")
        result = finnhub_social.get_social_sentiment_finnhub(
            "AAPL", "2026-05-01", "2026-05-08"
        )
        self.assertIn("Error fetching company news", result)
        self.assertIn("AAPL", result)


if __name__ == "__main__":
    unittest.main()
