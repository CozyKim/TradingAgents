# Social Data Vendor Integration — Design

**Date:** 2026-05-08
**Status:** Approved (brainstorming)
**Scope:** Replace the placeholder "social media analyst" pipeline (which currently reuses generic news APIs) with a dedicated social-data vendor layer.

---

## 1. Problem Statement

The current `social_media_analyst` (`tradingagents/agents/analysts/social_media_analyst.py`) exposes only `get_news` to the LLM. That tool routes to `yfinance` or `alpha_vantage`, both of which return generic news — not social media. Three concrete failure modes result:

1. **No social data source exists.** No Reddit, Twitter, StockTwits, or Finnhub integration in the codebase.
2. **System prompt vs tool signature mismatch.** The prompt advertises `get_news(query, start_date, end_date)`, but the real first argument is `ticker`. The LLM therefore passes free-form strings (e.g., `"AAPL social sentiment"`) and `yfinance` returns empty.
3. **`sentiment_report` only fills when `tool_calls == 0`.** Empty tool results trigger retries; rounds end with empty/short reports that propagate downstream to bull/bear/trader/risk.

End-user symptom: social analysis "keeps not working" — the report block is empty or near-empty across runs.

## 2. Goals / Non-Goals

**Goals**
- Real social-data vendor integration that returns aggregated sentiment metrics and recent retail-investor messages.
- Tool surface that prevents the prompt/signature mismatch by construction.
- Fits the existing `route_to_vendor` pattern with no architectural rewrite.
- Explicit, user-visible messages when keys are missing or rate limits hit (no silent empty results).

**Non-Goals (this spec)**
- Reddit (PRAW) integration — deferred to a follow-up.
- User-scoped encrypted key storage in the web service — environment-variable only for now.
- Korean retail-board sources (Naver 종토방, DCInside 주식갤러리) — out of scope; user runs US tickers.

## 3. Architecture Overview

A new `social_data` category is added alongside the existing `news_data` category. Routing reuses `route_to_vendor`. Two new tools are exposed to the LLM; the social analyst sees only those two.

**Vendor strategy (per tool, primary):**
| Tool | Primary vendor | Notes |
|---|---|---|
| `get_social_sentiment` | `finnhub` | Aggregated mention/score time series |
| `get_social_messages` | `stocktwits` | Public stream, no auth needed |

Routing is configured at the **tool level** (`tool_vendors` in `default_config.py`) since the two tools come from different vendors.

## 4. File Changes

| Action | Path | Purpose |
|---|---|---|
| New | `tradingagents/dataflows/finnhub_social.py` | Finnhub `/stock/social-sentiment` client + formatter |
| New | `tradingagents/dataflows/stocktwits.py` | StockTwits public stream client + formatter |
| New | `tradingagents/agents/utils/social_data_tools.py` | `@tool`-decorated `get_social_sentiment`, `get_social_messages` |
| Modify | `tradingagents/dataflows/interface.py` | Add `social_data` category, register tools in `VENDOR_METHODS` |
| Modify | `tradingagents/agents/analysts/social_media_analyst.py` | Replace tool list and prompt; bind to new tools only |
| Modify | `tradingagents/graph/trading_graph.py` | Replace `social` `ToolNode` contents |
| Modify | `tradingagents/default_config.py` | Add `data_vendors["social_data"]` and `tool_vendors` overrides |
| Modify | `.env.example` | Document `FINNHUB_API_KEY` |
| New | `tests/dataflows/test_finnhub_social.py` | Unit tests with mocked HTTP |
| New | `tests/dataflows/test_stocktwits.py` | Unit tests with mocked HTTP |
| New | `tests/dataflows/test_interface_social_routing.py` | Routing tests |
| New | `tests/agents/test_social_analyst.py` | Tool wiring + prompt assertions |

## 5. Tool Contracts

```python
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

@tool
def get_social_messages(
    ticker: Annotated[str, "Ticker symbol, e.g. AAPL"],
    limit: Annotated[int, "Maximum messages to return (default 30, max 50)"] = 30,
) -> str:
    """Recent retail-investor messages for a ticker (StockTwits public stream).

    Returns a markdown list of recent messages with body, created_at,
    and explicit Bullish/Bearish/None sentiment label per message.
    """
```

**Invariant:** the system prompt cites these signatures verbatim. The first positional argument is always `ticker` (a bare symbol, not free text). The prompt explicitly forbids free-form queries.

## 6. Vendor Module Specs

### 6.1 `finnhub_social.py`

- Endpoint: `GET https://finnhub.io/api/v1/stock/social-sentiment?symbol={ticker}&from={start_date}&to={end_date}&token={FINNHUB_API_KEY}`
- Auth: `FINNHUB_API_KEY` from environment.
- Response shape (Finnhub):
  ```json
  {
    "symbol": "AAPL",
    "reddit":  [{"atTime": "...", "mention": int, "positiveScore": float, "negativeScore": float, "score": float, ...}],
    "twitter": [...]
  }
  ```
- Formatter: emit a Markdown table per source (reddit, twitter) with columns `date | mentions | positive | negative | net`. Aggregate to per-day totals if multiple intraday entries exist.
- Error handling:
  - Missing key → return literal string `"FINNHUB_API_KEY not set; social sentiment unavailable. Set FINNHUB_API_KEY to enable."` (no exception — surfaced to LLM).
  - HTTP 401/403 → raise `FinnhubAuthError` (subclass of RuntimeError) → `route_to_vendor` falls through.
  - HTTP 429 → raise `FinnhubRateLimitError` (mirrors `AlphaVantageRateLimitError` pattern) → fallback chain.
  - Empty payload (`reddit == [] and twitter == []`) → return `"No social sentiment data for {ticker} between {start_date} and {end_date}."`
  - Network/timeout → `"Error fetching social sentiment for {ticker}: {exc}"`. (Surface but do not raise.)
- Timeout: 10s connect/read.

### 6.2 `stocktwits.py`

- Endpoint: `GET https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json?limit={limit}`
- Auth: none (public stream). Caller-side rate guard: at most 1 call per ticker per analyst run (LLM is told this in the prompt).
- Response shape: `{messages: [{body, created_at, entities: {sentiment: {basic: "Bullish"|"Bearish"|null}}, user: {username}}]}`
- Formatter: bullet list per message — `- [{created_at}] ({sentiment}) @{user}: {body}`. Truncate body to 280 chars.
- Error handling:
  - HTTP 404 → `"No StockTwits stream found for {ticker}."`
  - HTTP 429 → `"StockTwits rate-limited; try again later for {ticker}."` (no fallback vendor exists; surface as message.)
  - Empty `messages` → `"No StockTwits messages found for {ticker}."`
  - Network/timeout → `"Error fetching StockTwits messages for {ticker}: {exc}"`.
- Limit clamping: `limit = max(1, min(limit, 50))`.
- Timeout: 10s connect/read.

## 7. Routing & Configuration

`interface.py` additions:

```python
TOOLS_CATEGORIES["social_data"] = {
    "description": "Social media sentiment and retail messages",
    "tools": ["get_social_sentiment", "get_social_messages"],
}

VENDOR_LIST.extend(["finnhub", "stocktwits"])

VENDOR_METHODS["get_social_sentiment"] = {
    "finnhub": get_social_sentiment_finnhub,
}
VENDOR_METHODS["get_social_messages"] = {
    "stocktwits": get_social_messages_stocktwits,
}
```

`default_config.py` additions:

```python
"data_vendors": {
    ...,
    "social_data": "finnhub",   # category default; messages tool is overridden below
},
"tool_vendors": {
    "get_social_messages": "stocktwits",
},
```

`route_to_vendor` requires no changes — its existing primary/fallback iteration handles single-vendor tools cleanly (if the only registered vendor fails, it raises `RuntimeError("No available vendor for ...")`, which the tool wrapper catches and converts to a user-visible string before returning to the LLM).

## 8. Analyst Wiring

`social_media_analyst.py`:

```python
tools = [get_social_sentiment, get_social_messages]

system_message = (
    "You are a social media sentiment analyst. Use these tools:\n"
    "- get_social_sentiment(ticker, start_date, end_date): aggregated bullish/bearish "
    "scores and Reddit/Twitter mention trends.\n"
    "- get_social_messages(ticker, limit): recent retail-investor commentary.\n"
    "Always pass the bare ticker symbol (e.g. 'AAPL'). Never pass free-form "
    "queries. Synthesize sentiment direction, momentum shifts, and notable retail "
    "narratives. Append a Markdown summary table at the end of the report."
    + get_language_instruction()
)
```

`trading_graph.py` `_create_tool_nodes`:

```python
"social": ToolNode([get_social_sentiment, get_social_messages]),
```

The `if len(result.tool_calls) == 0: report = result.content` gating logic stays the same; with real data the LLM finishes its tool loop and produces a non-empty `sentiment_report`.

## 9. Error Surfacing Policy

Any vendor-side issue that prevents data retrieval **must return a string the LLM will see**, not a silent empty payload. This is the single most important behavioral change vs. the current code, which often handed back `"No news found for ..."` and let the LLM hallucinate. The strings above (`"FINNHUB_API_KEY not set; ..."`, etc.) are deliberately specific so the LLM either (a) reports the gap honestly or (b) falls back to the other tool.

## 10. Testing

**Vendor unit tests** (HTTP mocked via `responses` or `requests_mock`):
- `test_finnhub_social.py`: 200 with data, 200 with empty payload, 401 → `FinnhubAuthError`, 429 → `FinnhubRateLimitError`, missing-key path, timeout path.
- `test_stocktwits.py`: 200 with messages, 200 empty, 404, 429, malformed JSON, limit clamping (0, -1, 999 → clamped to 1/1/50).

**Routing test** (`test_interface_social_routing.py`):
- `route_to_vendor("get_social_sentiment", "AAPL", "2026-05-01", "2026-05-08")` invokes the finnhub function (assert via monkeypatch).
- `route_to_vendor("get_social_messages", "AAPL", 30)` invokes the stocktwits function.

**Analyst wiring test** (`test_social_analyst.py`):
- The tool list bound to the LLM contains exactly `get_social_sentiment`, `get_social_messages`.
- Rendered system message contains both signatures verbatim and the "bare ticker symbol" guard string.

**Coverage target:** ≥ 90% on the two new vendor modules.

## 11. Security & Secrets

- `FINNHUB_API_KEY` lives in `.env` (already gitignored). Documented in `.env.example` only with empty value.
- No keys logged. Vendor modules use `logging` for non-sensitive metadata only (status codes, ticker, date range).
- StockTwits is public; no secret.

## 12. Rollout

- Single PR. No feature flag — the swap is contained to the social analyst path.
- README/CLAUDE.md note added: "Social analysis requires `FINNHUB_API_KEY` for sentiment metrics; StockTwits stream works without keys."
- If `FINNHUB_API_KEY` is unset, social analysis still partially works via StockTwits + the explicit "key not set" message.

## ADDENDUM (2026-05-09): Finnhub endpoint substitution

After deployment we discovered that Finnhub's `/stock/social-sentiment` and
`/news-sentiment` endpoints are now **premium-only** (HTTP 403 on the free
tier). Free-tier `/quote`, `/company-news`, and `/stock/insider-sentiment`
continue to work.

**Decision:** keep the public tool name `get_social_sentiment` and the routing
wiring intact, but switch the underlying implementation
(`get_social_sentiment_finnhub`) from `/stock/social-sentiment` to
`/company-news`. The vendor now returns a daily-grouped markdown digest of the
top-N headlines (default 20, capped at 50) with summary text — the analyst LLM
infers sentiment from headline content and tone instead of consuming a
pre-computed mention/score table.

**Why this is acceptable:**
- The original goal — give the social analyst a real, dense, free-tier data
  source so `sentiment_report` stops landing empty — is preserved. AAPL over a
  7-day window returned 243 candidate items in live testing.
- The analyst system prompt was updated to advertise the new shape ("daily-
  grouped digest of company-news headlines"), keeping prompt and tool reality
  aligned (the original bug we set out to fix).
- StockTwits remains the retail-tone counterpart via `get_social_messages`, so
  the divergence-finding behavior of the analyst is unchanged.

**No behavioral surface change for the LLM tool contract:** function names,
arg names/order, return type, error-string conventions, and routing
(`route_to_vendor("get_social_sentiment", ...)`) all stay identical.

## 13. Out of Scope (tracked for follow-up)

- Reddit PRAW client (`get_social_sentiment` could grow a `reddit` vendor option later).
- Korean-language social sources (Naver 종토방, DCInside).
- Per-user encrypted key storage in the web layer.
- Caching of social responses (stale-while-revalidate). All fetches are live for now.
