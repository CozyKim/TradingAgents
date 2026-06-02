import logging
from typing import Annotated

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .alpha_vantage_common import AlphaVantageRateLimitError
from .finnhub_social import get_social_sentiment_finnhub
from .finnhub_common import FinnhubAuthError, FinnhubRateLimitError
from .naver_finance_board import get_social_messages_naver
from .stocktwits import get_social_messages_stocktwits

# Configuration and routing logic
from .config import get_config

_log = logging.getLogger(__name__)

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    },
    "social_data": {
        "description": "Social media sentiment metrics and retail messages",
        "tools": [
            "get_social_sentiment",
            "get_social_messages",
        ],
    },
}

VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "finnhub",
    "stocktwits",
]

# Mapping of methods to their vendor-specific implementations
VENDOR_METHODS = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
    # social_data
    "get_social_sentiment": {
        "finnhub": get_social_sentiment_finnhub,
    },
    "get_social_messages": {
        "stocktwits": get_social_messages_stocktwits,
        "naver": get_social_messages_naver,
    },
}

# Vendors whose coverage is limited to a single market. A vendor absent from
# this map is treated as global (always eligible). Used to skip vendors that
# cannot serve a given ticker's exchange — e.g. Finnhub's free tier returns
# HTTP 403 for Korean symbols, StockTwits has no Korean streams, and the Naver
# 종목토론방 is Korea-only.
_VENDOR_MARKET = {
    "finnhub": "us",  # free tier: non-US symbols 403
    "stocktwits": "us",  # no Korean streams
    "naver": "kr",  # 종목토론방: .KS/.KQ only
}


def _is_korean_ticker(symbol: object) -> bool:
    """Return True for Yahoo-style Korean tickers (``005930.KS`` / ``035720.KQ``)."""
    return isinstance(symbol, str) and symbol.strip().upper().endswith((".KS", ".KQ"))


def _vendor_supports_ticker(vendor: str, ticker: object) -> bool:
    """Return True unless ``vendor`` is market-scoped and ``ticker`` is out of scope.

    Non-string first args (e.g. ``get_global_news`` takes a date) and vendors
    without a market scope are always considered supported.
    """
    market = _VENDOR_MARKET.get(vendor)
    if market is None or not isinstance(ticker, str):
        return True
    is_kr = _is_korean_ticker(ticker)
    return is_kr if market == "kr" else not is_kr


def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method."""
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category
    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    return config.get("data_vendors", {}).get(category, "default")

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in VENDOR_METHODS:
        raise ValueError(f"Method '{method}' not supported")

    # Build fallback chain: primary vendors first, then remaining available vendors
    all_available_vendors = list(VENDOR_METHODS[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    ticker = args[0] if args else None
    last_error: Exception | None = None

    for vendor in fallback_vendors:
        if vendor not in VENDOR_METHODS[method]:
            continue
        # Skip vendors that can't serve this ticker's market (e.g. Finnhub for
        # Korean tickers, Naver for US tickers) so we fall through to one that can.
        if not _vendor_supports_ticker(vendor, ticker):
            continue

        vendor_impl = VENDOR_METHODS[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except (
            AlphaVantageRateLimitError,
            FinnhubRateLimitError,
            FinnhubAuthError,
        ) as exc:
            # Non-fatal vendor failures — rate limits (429) and auth/permission
            # errors (401/403: premium-only endpoint, missing/invalid key).
            # Fall through to the next vendor instead of aborting the run.
            last_error = exc
            _log.warning(
                "vendor '%s' failed for '%s' (%s); trying next vendor",
                vendor,
                method,
                exc,
            )
            continue

    # No vendor could serve the request. Return an LLM-readable notice rather
    # than raising, so one unavailable data source degrades gracefully instead
    # of killing the whole multi-agent run.
    detail = f" (last error: {last_error})" if last_error is not None else ""
    _log.warning("no available vendor for '%s'%s", method, detail)
    return (
        f"Data for '{method}' is currently unavailable from all configured "
        f"vendors{detail}. Continue your analysis using other available "
        f"information and note this gap."
    )
