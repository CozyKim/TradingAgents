# Social Data Vendor Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder "social media analyst" tool surface with real Finnhub + StockTwits integrations so `sentiment_report` is consistently populated.

**Architecture:** New `social_data` category with two LLM tools (`get_social_sentiment`, `get_social_messages`) that route to dedicated vendor modules via the existing `route_to_vendor` helper. The social analyst is rewired to bind only these two tools, eliminating the prompt/signature mismatch that caused empty reports.

**Tech Stack:** Python 3.10+, `requests`, `unittest` + `unittest.mock.patch`, LangChain `@tool`, LangGraph `ToolNode`.

**Spec reference:** `docs/superpowers/specs/2026-05-08-social-data-vendor-design.md`

---

## File Structure

| Path | Responsibility |
|---|---|
| `tradingagents/dataflows/finnhub_common.py` (new) | API key resolver, error classes, shared HTTP helper for Finnhub |
| `tradingagents/dataflows/finnhub_social.py` (new) | `get_social_sentiment_finnhub` — fetch + format `/stock/social-sentiment` |
| `tradingagents/dataflows/stocktwits.py` (new) | `get_social_messages_stocktwits` — fetch + format StockTwits public stream |
| `tradingagents/agents/utils/social_data_tools.py` (new) | LangChain `@tool` wrappers `get_social_sentiment`, `get_social_messages` |
| `tradingagents/dataflows/interface.py` (modify) | Register category, vendors, methods |
| `tradingagents/agents/analysts/social_media_analyst.py` (modify) | Bind new tools; rewrite system message with exact signatures |
| `tradingagents/graph/trading_graph.py` (modify) | Replace `social` `ToolNode` contents and import |
| `tradingagents/default_config.py` (modify) | Add `social_data` category and `tool_vendors` overrides |
| `.env.example` (modify) | Document `FINNHUB_API_KEY` |
| `tests/dataflows/test_finnhub_social.py` (new) | Vendor unit tests |
| `tests/dataflows/test_stocktwits.py` (new) | Vendor unit tests |
| `tests/dataflows/test_interface_social_routing.py` (new) | Routing tests |
| `tests/agents/test_social_analyst.py` (new) | Analyst wiring tests |

---

## Task 1: Finnhub Common Helper + Social Sentiment Vendor

**Files:**
- Create: `tradingagents/dataflows/finnhub_common.py`
- Create: `tradingagents/dataflows/finnhub_social.py`
- Create: `tests/dataflows/__init__.py` (empty, marks package)
- Create: `tests/dataflows/test_finnhub_social.py`

- [ ] **Step 1.1: Create empty test directory marker**

```bash
mkdir -p tests/dataflows
touch tests/dataflows/__init__.py
```

- [ ] **Step 1.2: Write the failing tests**

Create `tests/dataflows/test_finnhub_social.py`:

```python
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
```

- [ ] **Step 1.3: Run tests to confirm they fail**

Run: `python -m pytest tests/dataflows/test_finnhub_social.py -v`
Expected: ImportError (modules `finnhub_common` / `finnhub_social` don't exist).

- [ ] **Step 1.4: Implement `finnhub_common.py`**

Create `tradingagents/dataflows/finnhub_common.py`:

```python
"""Shared Finnhub HTTP plumbing: auth, error classes, request helper."""

from __future__ import annotations

import os
import logging
from typing import Any

import requests

API_BASE_URL = "https://finnhub.io/api/v1"
_TIMEOUT_SECONDS = 10
_log = logging.getLogger(__name__)


class FinnhubAuthError(RuntimeError):
    """Raised when Finnhub returns 401/403 (bad/missing key)."""


class FinnhubRateLimitError(RuntimeError):
    """Raised when Finnhub returns 429 (rate limit exceeded)."""


def get_api_key() -> str | None:
    """Return FINNHUB_API_KEY env var or None when unset."""
    key = os.getenv("FINNHUB_API_KEY")
    return key.strip() if key and key.strip() else None


def finnhub_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET helper that adds the API key and maps HTTP errors to typed exceptions.

    Args:
        path: Path under the API base, e.g. "/stock/social-sentiment".
        params: Query parameters (must NOT include "token").

    Returns:
        The parsed JSON body (always a dict; list payloads are wrapped under "items").

    Raises:
        FinnhubAuthError: 401/403 response.
        FinnhubRateLimitError: 429 response.
        requests.RequestException: network-level failure (caller decides how to surface).
    """
    key = get_api_key()
    if not key:
        raise FinnhubAuthError("FINNHUB_API_KEY not set")

    query = dict(params)
    query["token"] = key
    url = f"{API_BASE_URL}{path}"
    _log.debug("finnhub_get path=%s params=%s", path, {k: v for k, v in params.items()})
    resp = requests.get(url, params=query, timeout=_TIMEOUT_SECONDS)

    if resp.status_code in (401, 403):
        raise FinnhubAuthError(f"Finnhub auth failed (HTTP {resp.status_code}).")
    if resp.status_code == 429:
        raise FinnhubRateLimitError("Finnhub rate limit exceeded (HTTP 429).")
    resp.raise_for_status()

    body = resp.json()
    if isinstance(body, list):
        return {"items": body}
    return body
```

- [ ] **Step 1.5: Implement `finnhub_social.py`**

Create `tradingagents/dataflows/finnhub_social.py`:

```python
"""Finnhub social sentiment vendor."""

from __future__ import annotations

import logging
from collections import defaultdict

import requests

from .finnhub_common import (
    FinnhubAuthError,
    FinnhubRateLimitError,
    finnhub_get,
    get_api_key,
)

_log = logging.getLogger(__name__)


def _aggregate_by_day(entries: list[dict]) -> list[dict]:
    """Collapse intraday entries to daily totals (date -> mentions, scores)."""
    by_day: dict[str, dict] = defaultdict(lambda: {"mentions": 0, "pos": 0.0, "neg": 0.0, "n": 0})
    for entry in entries:
        at = str(entry.get("atTime") or entry.get("date") or "")[:10]
        if not at:
            continue
        bucket = by_day[at]
        bucket["mentions"] += int(entry.get("mention", 0) or 0)
        bucket["pos"] += float(entry.get("positiveScore", 0) or 0)
        bucket["neg"] += float(entry.get("negativeScore", 0) or 0)
        bucket["n"] += 1
    out = []
    for date, b in sorted(by_day.items()):
        n = max(b["n"], 1)
        out.append({
            "date": date,
            "mentions": b["mentions"],
            "positive": round(b["pos"] / n, 3),
            "negative": round(b["neg"] / n, 3),
            "net": round((b["pos"] - b["neg"]) / n, 3),
        })
    return out


def _render_table(title: str, rows: list[dict]) -> str:
    if not rows:
        return f"#### {title}\n\n_No data._\n"
    out = [f"#### {title}", "", "| date | mentions | positive | negative | net |",
           "|---|---:|---:|---:|---:|"]
    for r in rows:
        out.append(f"| {r['date']} | {r['mentions']} | {r['positive']} | {r['negative']} | {r['net']} |")
    out.append("")
    return "\n".join(out)


def get_social_sentiment_finnhub(ticker: str, start_date: str, end_date: str) -> str:
    """Fetch Finnhub /stock/social-sentiment and render a markdown report.

    Args:
        ticker: Bare ticker symbol (e.g. "AAPL").
        start_date: yyyy-mm-dd inclusive.
        end_date: yyyy-mm-dd inclusive.

    Returns:
        A markdown string. On missing key or network error, returns a user-visible
        explanation string (not an exception). On 401/403/429, raises so
        route_to_vendor can fall through.
    """
    if not get_api_key():
        return "FINNHUB_API_KEY not set; social sentiment unavailable. Set FINNHUB_API_KEY to enable."

    try:
        body = finnhub_get(
            "/stock/social-sentiment",
            {"symbol": ticker, "from": start_date, "to": end_date},
        )
    except (FinnhubAuthError, FinnhubRateLimitError):
        raise
    except requests.RequestException as exc:
        _log.warning("finnhub social network error: %s", exc)
        return f"Error fetching social sentiment for {ticker}: {exc}"

    reddit = body.get("reddit") or []
    twitter = body.get("twitter") or []
    if not reddit and not twitter:
        return f"No social sentiment data for {ticker} between {start_date} and {end_date}."

    parts = [
        f"## Social Sentiment — {ticker} ({start_date} → {end_date})",
        "",
        _render_table("Reddit", _aggregate_by_day(reddit)),
        _render_table("Twitter", _aggregate_by_day(twitter)),
    ]
    return "\n".join(parts)
```

- [ ] **Step 1.6: Run tests to confirm they pass**

Run: `python -m pytest tests/dataflows/test_finnhub_social.py -v`
Expected: 6 tests pass.

- [ ] **Step 1.7: Commit**

```bash
git add tradingagents/dataflows/finnhub_common.py \
        tradingagents/dataflows/finnhub_social.py \
        tests/dataflows/__init__.py \
        tests/dataflows/test_finnhub_social.py
git commit -m "feat(dataflows): add finnhub social sentiment vendor

신규 finnhub_common(인증/에러/HTTP 헬퍼) + finnhub_social(/stock/social-sentiment
파서·markdown 포맷). 키 누락은 명시 메시지로 LLM에 노출, 401/429는 typed
exception으로 폴백 체인 위임.
"
```

---

## Task 2: StockTwits Public Stream Vendor

**Files:**
- Create: `tradingagents/dataflows/stocktwits.py`
- Create: `tests/dataflows/test_stocktwits.py`

- [ ] **Step 2.1: Write the failing tests**

Create `tests/dataflows/test_stocktwits.py`:

```python
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
```

- [ ] **Step 2.2: Run tests to confirm they fail**

Run: `python -m pytest tests/dataflows/test_stocktwits.py -v`
Expected: ImportError (`stocktwits` module not found).

- [ ] **Step 2.3: Implement `stocktwits.py`**

Create `tradingagents/dataflows/stocktwits.py`:

```python
"""StockTwits public stream vendor (no auth required)."""

from __future__ import annotations

import logging

import requests

API_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_TIMEOUT_SECONDS = 10
_BODY_MAX = 280
_log = logging.getLogger(__name__)


def _truncate(text: str, limit: int = _BODY_MAX) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def get_social_messages_stocktwits(ticker: str, limit: int = 30) -> str:
    """Fetch recent retail-investor messages for a ticker from StockTwits.

    Args:
        ticker: Bare ticker symbol (e.g. "AAPL").
        limit: Max messages, clamped to [1, 50].

    Returns:
        A markdown bullet list, or an explicit no-data message. Network-level
        errors are caught and surfaced as readable strings (not raised) — there
        is no fallback vendor for this method.
    """
    safe_limit = max(1, min(int(limit), 50))
    url = API_URL.format(ticker=ticker)

    try:
        resp = requests.get(url, params={"limit": safe_limit}, timeout=_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        _log.warning("stocktwits network error: %s", exc)
        return f"Error fetching StockTwits messages for {ticker}: {exc}"

    if resp.status_code == 404:
        return f"No StockTwits stream found for {ticker}."
    if resp.status_code == 429:
        return f"StockTwits rate-limited; try again later for {ticker}."

    try:
        resp.raise_for_status()
        body = resp.json()
    except (requests.RequestException, ValueError) as exc:
        return f"Error fetching StockTwits messages for {ticker}: {exc}"

    messages = body.get("messages") or []
    if not messages:
        return f"No StockTwits messages found for {ticker}."

    lines = [f"## StockTwits — {ticker} (last {len(messages)} messages)", ""]
    for m in messages:
        ts = m.get("created_at", "")
        user = (m.get("user") or {}).get("username", "?")
        sentiment_obj = (m.get("entities") or {}).get("sentiment") or {}
        sentiment = sentiment_obj.get("basic") if isinstance(sentiment_obj, dict) else None
        body_txt = _truncate(m.get("body", ""))
        lines.append(f"- [{ts}] ({sentiment}) @{user}: {body_txt}")
    return "\n".join(lines)
```

- [ ] **Step 2.4: Run tests to confirm they pass**

Run: `python -m pytest tests/dataflows/test_stocktwits.py -v`
Expected: 8 tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add tradingagents/dataflows/stocktwits.py tests/dataflows/test_stocktwits.py
git commit -m "feat(dataflows): add stocktwits public stream vendor

StockTwits 공개 스트림 클라이언트. 인증 불필요, limit clamp [1,50],
404/429/네트워크 에러는 LLM 가시 메시지로 변환.
"
```

---

## Task 3: Interface Routing Registration

**Files:**
- Modify: `tradingagents/dataflows/interface.py`
- Create: `tests/dataflows/test_interface_social_routing.py`

- [ ] **Step 3.1: Write the failing routing tests**

Create `tests/dataflows/test_interface_social_routing.py`:

```python
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
```

- [ ] **Step 3.2: Run tests to confirm they fail**

Run: `python -m pytest tests/dataflows/test_interface_social_routing.py -v`
Expected: AssertionError (`social_data` not in `TOOLS_CATEGORIES`).

- [ ] **Step 3.3: Modify `interface.py`**

In `tradingagents/dataflows/interface.py`:

(a) Add import for the new vendor functions next to the existing vendor imports near the top of the file (after the `from .alpha_vantage_common import AlphaVantageRateLimitError` line):

```python
from .finnhub_social import get_social_sentiment_finnhub
from .finnhub_common import FinnhubRateLimitError
from .stocktwits import get_social_messages_stocktwits
```

(b) Add a `social_data` entry inside `TOOLS_CATEGORIES`, right after the existing `news_data` entry (preserve trailing comma style):

```python
    "social_data": {
        "description": "Social media sentiment metrics and retail messages",
        "tools": [
            "get_social_sentiment",
            "get_social_messages",
        ],
    },
```

(c) Extend `VENDOR_LIST`:

```python
VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
    "finnhub",
    "stocktwits",
]
```

(d) Add to `VENDOR_METHODS` (after the existing `get_insider_transactions` entry, inside the same dict):

```python
    # social_data
    "get_social_sentiment": {
        "finnhub": get_social_sentiment_finnhub,
    },
    "get_social_messages": {
        "stocktwits": get_social_messages_stocktwits,
    },
```

(e) Update `route_to_vendor` to also pass through `FinnhubRateLimitError` (treat like `AlphaVantageRateLimitError`). Find the existing `except AlphaVantageRateLimitError:` line and change it to:

```python
        except (AlphaVantageRateLimitError, FinnhubRateLimitError):
            continue  # Only rate limits trigger fallback
```

- [ ] **Step 3.4: Run tests to confirm they pass**

Run: `python -m pytest tests/dataflows/test_interface_social_routing.py -v`
Expected: 4 tests pass.

- [ ] **Step 3.5: Sanity-run the broader dataflows test suite**

Run: `python -m pytest tests/dataflows/ -v`
Expected: All Task 1+2+3 tests pass.

- [ ] **Step 3.6: Commit**

```bash
git add tradingagents/dataflows/interface.py \
        tests/dataflows/test_interface_social_routing.py
git commit -m "feat(dataflows): register social_data category and routing

interface.py에 social_data 카테고리 + finnhub/stocktwits 벤더 등록.
FinnhubRateLimitError를 AlphaVantageRateLimitError와 동일하게 폴백 트리거로 처리.
"
```

---

## Task 4: LangChain Tool Wrappers

**Files:**
- Create: `tradingagents/agents/utils/social_data_tools.py`
- Modify: `tests/dataflows/test_interface_social_routing.py` (extend with tool-level test)

- [ ] **Step 4.1: Add a failing tool-wrapper test**

Append to `tests/dataflows/test_interface_social_routing.py`:

```python
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
```

- [ ] **Step 4.2: Run tests to confirm they fail**

Run: `python -m pytest tests/dataflows/test_interface_social_routing.py::SocialToolWrapperTests -v`
Expected: ImportError (module `social_data_tools` not found).

- [ ] **Step 4.3: Create `social_data_tools.py`**

Create `tradingagents/agents/utils/social_data_tools.py`:

```python
"""LangChain tool wrappers for the social_data category."""

from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_social_sentiment(
    ticker: Annotated[str, "Ticker symbol, e.g. AAPL"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Aggregated social sentiment metrics for a ticker.

    Returns a markdown report containing daily Reddit and Twitter mention
    counts plus bullish/bearish score breakdowns within [start_date, end_date].
    """
    return route_to_vendor("get_social_sentiment", ticker, start_date, end_date)


@tool
def get_social_messages(
    ticker: Annotated[str, "Ticker symbol, e.g. AAPL"],
    limit: Annotated[int, "Maximum messages to return (default 30, max 50)"] = 30,
) -> str:
    """Recent retail-investor messages for a ticker (StockTwits public stream).

    Returns a markdown list of recent messages with body, created_at, and an
    explicit Bullish/Bearish/None sentiment label per message.
    """
    return route_to_vendor("get_social_messages", ticker, limit)
```

- [ ] **Step 4.4: Run tests to confirm they pass**

Run: `python -m pytest tests/dataflows/test_interface_social_routing.py -v`
Expected: 6 tests pass (4 routing + 2 tool wrappers).

- [ ] **Step 4.5: Commit**

```bash
git add tradingagents/agents/utils/social_data_tools.py \
        tests/dataflows/test_interface_social_routing.py
git commit -m "feat(agents/utils): expose social tools as LangChain @tool wrappers

get_social_sentiment, get_social_messages를 route_to_vendor에 위임하는
LangChain tool로 노출. 첫 인자는 명확히 ticker로 고정.
"
```

---

## Task 5: Wire Analyst, Graph, Config, and Env

**Files:**
- Modify: `tradingagents/agents/analysts/social_media_analyst.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Modify: `tradingagents/default_config.py`
- Modify: `.env.example`
- Create: `tests/agents/__init__.py` (if missing)
- Create: `tests/agents/test_social_analyst.py`

- [ ] **Step 5.1: Ensure `tests/agents/` package marker exists**

Run: `ls tests/agents/__init__.py 2>/dev/null || (mkdir -p tests/agents && touch tests/agents/__init__.py)`

- [ ] **Step 5.2: Write the failing analyst-wiring tests**

Create `tests/agents/test_social_analyst.py`:

```python
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
        self.assertIn("get_social_messages(ticker, limit)", src)
        self.assertIn("bare ticker symbol", src)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5.3: Run tests to confirm they fail**

Run: `python -m pytest tests/agents/test_social_analyst.py -v`
Expected: failures — current analyst still binds `get_news`, system prompt lacks new signatures.

- [ ] **Step 5.4: Rewrite `social_media_analyst.py`**

Replace the contents of `tradingagents/agents/analysts/social_media_analyst.py` with:

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.agents.utils.social_data_tools import (
    get_social_messages,
    get_social_sentiment,
)


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [get_social_sentiment, get_social_messages]

        system_message = (
            "You are a social media sentiment analyst. Use these tools:\n"
            "- get_social_sentiment(ticker, start_date, end_date): aggregated bullish/"
            "bearish scores and Reddit/Twitter mention trends for the date range.\n"
            "- get_social_messages(ticker, limit): recent retail-investor commentary "
            "from StockTwits.\n"
            "Always pass the bare ticker symbol (e.g. 'AAPL'). Never pass free-form "
            "queries. Synthesize sentiment direction, momentum shifts, notable retail "
            "narratives, and any divergence between aggregate sentiment and individual "
            "messages. Append a Markdown summary table at the end of the report."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    return social_media_analyst_node
```

- [ ] **Step 5.5: Update `trading_graph.py` ToolNode**

In `tradingagents/graph/trading_graph.py`:

(a) Replace the existing `from tradingagents.agents.utils.agent_utils import (...)` line that imports `get_news` for the social branch — keep `get_news` for the news branch but add the new social imports. Add this import block (location: alongside other agent_utils imports near the top):

```python
from tradingagents.agents.utils.social_data_tools import (
    get_social_messages,
    get_social_sentiment,
)
```

(b) Replace the `"social"` ToolNode in `_create_tool_nodes`:

```python
            "social": ToolNode(
                [
                    get_social_sentiment,
                    get_social_messages,
                ]
            ),
```

- [ ] **Step 5.6: Update `default_config.py`**

In `tradingagents/default_config.py`, extend the existing `data_vendors` and `tool_vendors` dicts:

```python
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
        "social_data": "finnhub",
    },
    "tool_vendors": {
        "get_social_messages": "stocktwits",
    },
```

- [ ] **Step 5.7: Update `.env.example`**

In `.env.example`, append after the existing LLM provider section:

```
# === Social Data Vendors ===
# Finnhub free tier: 60 calls/min. Required for get_social_sentiment.
FINNHUB_API_KEY=
```

- [ ] **Step 5.8: Run analyst wiring tests**

Run: `python -m pytest tests/agents/test_social_analyst.py -v`
Expected: 2 tests pass.

- [ ] **Step 5.9: Run the full new test surface**

Run: `python -m pytest tests/dataflows/ tests/agents/test_social_analyst.py -v`
Expected: all tests pass (Task 1: 6, Task 2: 8, Task 3+4: 6, Task 5: 2 = 22).

- [ ] **Step 5.10: Sanity import check on the graph**

Run: `python -c "from tradingagents.graph.trading_graph import TradingAgentsGraph; print('OK')"`
Expected: prints `OK` (no import error from the new social tool wiring).

- [ ] **Step 5.11: Commit**

```bash
git add tradingagents/agents/analysts/social_media_analyst.py \
        tradingagents/graph/trading_graph.py \
        tradingagents/default_config.py \
        .env.example \
        tests/agents/__init__.py \
        tests/agents/test_social_analyst.py
git commit -m "feat(social-analyst): wire finnhub+stocktwits tools into analyst and graph

소셜 애널리스트가 get_social_sentiment / get_social_messages만 노출하도록 교체.
프롬프트 시그니처와 도구 시그니처가 일치하므로 LLM의 ticker 인자 혼동 제거.
default_config에 social_data 카테고리 추가, .env.example에 FINNHUB_API_KEY 문서화.
"
```

---

## Self-Review

**Spec coverage:**
- §3 architecture (new category + 2 tools) → Tasks 3, 4
- §4 file changes → Tasks 1–5 (all 13 files in spec are addressed)
- §5 tool contracts → Task 4 (`social_data_tools.py`)
- §6.1 finnhub vendor + error matrix → Task 1 (test cases cover missing-key, 401, 429, empty, network)
- §6.2 stocktwits vendor + clamping/truncation → Task 2 (test cases cover 404, 429, empty, clamp 0/999, truncation)
- §7 routing/config → Tasks 3, 5
- §8 analyst wiring → Task 5
- §9 error surfacing policy → assertions in Task 1/2 tests verify literal strings
- §10 testing strategy → vendor unit tests, routing test, analyst wiring test all present
- §11 secrets → `.env.example` documented in Task 5; no key logging in vendor code

**Placeholder scan:** No TBD/TODO/"add appropriate handling". All test bodies are written out; all code blocks are complete.

**Type consistency:**
- Function names: `get_social_sentiment_finnhub` / `get_social_messages_stocktwits` — used identically in vendor module, interface registration (Task 3.3 step d), and routing tests (Task 3.1).
- Tool names: `get_social_sentiment` / `get_social_messages` — used identically in `social_data_tools.py`, ToolNode (5.5), analyst (5.4), and routing test assertions.
- Error classes: `FinnhubAuthError`, `FinnhubRateLimitError` — defined in `finnhub_common.py` (1.4), imported in interface (3.3 step a) and tests (1.2).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-08-social-data-vendor.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task with review between tasks; isolates context, easier course-correction.
2. **Inline Execution** — execute all tasks in this session via `superpowers:executing-plans`, batched with checkpoints.

Which approach do you prefer?
