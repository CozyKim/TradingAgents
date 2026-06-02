"""route_to_vendor must degrade gracefully instead of aborting an agent run.

A Finnhub 401/403 (premium-only endpoint, or missing/invalid key) raises
``FinnhubAuthError`` from the vendor impl. Previously that exception — and the
"all vendors exhausted" case — propagated out of the data layer, through the
LangGraph ToolNode, and killed the entire multi-agent stream. These tests pin
the contract that auth/rate-limit failures are non-fatal: fall through to the
next vendor, and when none can serve, return an LLM-readable string instead of
raising.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tradingagents.dataflows import interface
from tradingagents.dataflows.finnhub_common import (
    FinnhubAuthError,
    FinnhubRateLimitError,
)


class RouteToVendorResilienceTests(unittest.TestCase):
    def test_auth_error_single_vendor_returns_graceful_string(self):
        # get_social_sentiment has only the finnhub vendor. A 403 must not raise.
        original = interface.VENDOR_METHODS["get_social_sentiment"]["finnhub"]
        boom = MagicMock(side_effect=FinnhubAuthError("Finnhub auth failed (HTTP 403)."))
        interface.VENDOR_METHODS["get_social_sentiment"]["finnhub"] = boom
        try:
            out = interface.route_to_vendor(
                "get_social_sentiment", "AAPL", "2026-05-01", "2026-05-08"
            )
        finally:
            interface.VENDOR_METHODS["get_social_sentiment"]["finnhub"] = original

        self.assertIsInstance(out, str)
        self.assertIn("unavailable", out.lower())

    def test_auth_error_falls_through_to_next_vendor(self):
        # Primary vendor 403s; routing must fall through to the working secondary.
        methods = interface.VENDOR_METHODS["get_fundamentals"]
        orig_av = methods["alpha_vantage"]
        orig_yf = methods["yfinance"]
        methods["alpha_vantage"] = MagicMock(
            side_effect=FinnhubAuthError("auth failed")
        )
        methods["yfinance"] = MagicMock(return_value="YF_OK")
        try:
            with patch.object(
                interface, "get_vendor", return_value="alpha_vantage,yfinance"
            ):
                out = interface.route_to_vendor(
                    "get_fundamentals", "AAPL", "2026-05-08"
                )
        finally:
            methods["alpha_vantage"] = orig_av
            methods["yfinance"] = orig_yf

        self.assertEqual(out, "YF_OK")

    def test_all_vendors_exhausted_returns_graceful_string(self):
        # Every vendor fails (rate limit / auth): graceful string, never RuntimeError.
        methods = interface.VENDOR_METHODS["get_fundamentals"]
        orig_av = methods["alpha_vantage"]
        orig_yf = methods["yfinance"]
        methods["alpha_vantage"] = MagicMock(
            side_effect=FinnhubRateLimitError("429")
        )
        methods["yfinance"] = MagicMock(side_effect=FinnhubAuthError("403"))
        try:
            with patch.object(
                interface, "get_vendor", return_value="alpha_vantage,yfinance"
            ):
                out = interface.route_to_vendor(
                    "get_fundamentals", "AAPL", "2026-05-08"
                )
        finally:
            methods["alpha_vantage"] = orig_av
            methods["yfinance"] = orig_yf

        self.assertIsInstance(out, str)
        self.assertIn("unavailable", out.lower())


if __name__ == "__main__":
    unittest.main()
