import unittest
from unittest.mock import MagicMock, patch

from tradingagents.dataflows import interface


def _swap_messages_vendors(stocktwits_fn, naver_fn):
    """Install mock stocktwits/naver impls for get_social_messages; return restorer."""
    methods = interface.VENDOR_METHODS["get_social_messages"]
    orig_st = methods.get("stocktwits")
    orig_naver = methods.get("naver")
    methods["stocktwits"] = stocktwits_fn
    methods["naver"] = naver_fn

    def restore():
        if orig_st is None:
            methods.pop("stocktwits", None)
        else:
            methods["stocktwits"] = orig_st
        if orig_naver is None:
            methods.pop("naver", None)
        else:
            methods["naver"] = orig_naver

    return restore


class SocialRoutingTests(unittest.TestCase):
    def test_social_data_category_registered(self):
        self.assertIn("social_data", interface.TOOLS_CATEGORIES)
        tools = interface.TOOLS_CATEGORIES["social_data"]["tools"]
        self.assertIn("get_social_sentiment", tools)
        self.assertIn("get_social_messages", tools)

    def test_get_social_sentiment_us_routes_to_finnhub(self):
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

    def test_get_social_messages_us_routes_to_stocktwits(self):
        # US ticker: StockTwits (the Korea-only Naver vendor must be skipped).
        mock_st = MagicMock(return_value="ST_OK")
        mock_naver = MagicMock(return_value="NAVER_OK")
        restore = _swap_messages_vendors(mock_st, mock_naver)
        try:
            out = interface.route_to_vendor("get_social_messages", "AAPL", 30)
        finally:
            restore()

        self.assertEqual(out, "ST_OK")
        mock_st.assert_called_once_with("AAPL", 30)
        mock_naver.assert_not_called()

    def test_get_social_messages_korean_skips_stocktwits_routes_to_naver(self):
        # Korean ticker: StockTwits has no coverage, so route to Naver 종목토론방.
        mock_st = MagicMock(return_value="ST_OK")
        mock_naver = MagicMock(return_value="NAVER_OK")
        restore = _swap_messages_vendors(mock_st, mock_naver)
        try:
            out = interface.route_to_vendor("get_social_messages", "005930.KS", 30)
        finally:
            restore()

        self.assertEqual(out, "NAVER_OK")
        mock_naver.assert_called_once_with("005930.KS", 30)
        mock_st.assert_not_called()

    def test_get_category_for_social_methods(self):
        self.assertEqual(
            interface.get_category_for_method("get_social_sentiment"), "social_data"
        )
        self.assertEqual(
            interface.get_category_for_method("get_social_messages"), "social_data"
        )


class SocialToolWrapperTests(unittest.TestCase):
    def test_get_social_sentiment_tool_us_invokes_router(self):
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

    def test_get_social_sentiment_tool_korean_returns_guidance(self):
        from tradingagents.agents.utils.social_data_tools import get_social_sentiment

        with patch(
            "tradingagents.agents.utils.social_data_tools.route_to_vendor",
            return_value="ROUTED",
        ) as mock_route:
            result = get_social_sentiment.invoke(
                {
                    "ticker": "005930.KS",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-08",
                }
            )
            # Korean tickers have no news-sentiment source; the tool steers the
            # LLM to get_social_messages (종목토론방) instead of calling a vendor.
            self.assertIn("get_social_messages", result)
            mock_route.assert_not_called()

    def test_get_social_messages_tool_invokes_router(self):
        from tradingagents.agents.utils.social_data_tools import get_social_messages

        with patch(
            "tradingagents.agents.utils.social_data_tools.route_to_vendor",
            return_value="ROUTED",
        ) as mock_route:
            result = get_social_messages.invoke({"ticker": "AAPL", "limit": 25})
            self.assertEqual(result, "ROUTED")
            mock_route.assert_called_once_with(
                "get_social_messages", "AAPL", 25, sort="latest", days=None
            )

    def test_get_social_messages_korean_default_is_views_last_3d(self):
        from tradingagents.agents.utils.social_data_tools import get_social_messages

        with patch(
            "tradingagents.agents.utils.social_data_tools.route_to_vendor",
            return_value="ROUTED",
        ) as mock_route:
            get_social_messages.invoke({"ticker": "005930.KS"})
            # Korean tickers default to most-viewed posts of the last 3 days.
            mock_route.assert_called_once_with(
                "get_social_messages", "005930.KS", 30, sort="views", days=3
            )

    def test_get_social_messages_korean_explicit_sort_overrides_default(self):
        from tradingagents.agents.utils.social_data_tools import get_social_messages

        with patch(
            "tradingagents.agents.utils.social_data_tools.route_to_vendor",
            return_value="ROUTED",
        ) as mock_route:
            get_social_messages.invoke(
                {"ticker": "005930.KS", "limit": 20, "sort": "latest"}
            )
            # Explicit sort wins; the 3-day default window still applies.
            mock_route.assert_called_once_with(
                "get_social_messages", "005930.KS", 20, sort="latest", days=3
            )

    def test_get_social_messages_tool_passes_days(self):
        from tradingagents.agents.utils.social_data_tools import get_social_messages

        with patch(
            "tradingagents.agents.utils.social_data_tools.route_to_vendor",
            return_value="ROUTED",
        ) as mock_route:
            get_social_messages.invoke(
                {"ticker": "005930.KS", "sort": "views", "days": 3}
            )
            # "지난 3일 조회순" → views + 3-day window forwarded to the vendor.
            mock_route.assert_called_once_with(
                "get_social_messages", "005930.KS", 30, sort="views", days=3
            )

    def test_get_social_messages_default_limit_is_30(self):
        from tradingagents.agents.utils.social_data_tools import get_social_messages

        with patch(
            "tradingagents.agents.utils.social_data_tools.route_to_vendor",
            return_value="ROUTED",
        ) as mock_route:
            get_social_messages.invoke({"ticker": "AAPL"})
            mock_route.assert_called_once_with(
                "get_social_messages", "AAPL", 30, sort="latest", days=None
            )


if __name__ == "__main__":
    unittest.main()
