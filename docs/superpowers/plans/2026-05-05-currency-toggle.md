# Currency Toggle (USD/KRW) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 가격 표시에 통화 기호(`$`/`₩`)를 명시하고, 사이드바/모바일 헤더의 글로벌 토글로 USD ↔ KRW 표시 단위를 전환한다. 환율은 yfinance `KRW=X`로 백엔드가 24h 캐시한다.

**Architecture:** USD 네이티브 가격은 DB/API에 그대로 보관하고, 표시 시점에 React Context의 통화 상태와 환율을 받아 클라이언트 사이드에서 환산만 수행한다. 환율 fetch는 별도 엔드포인트로 분리(가격 5분 TTL, 환율 24h TTL).

**Tech Stack:** FastAPI + Pydantic + yfinance (백엔드), Next.js 14 + React Query + React Context + Tailwind (프론트엔드). pytest (백엔드 테스트), node:test + typescript transpile (프론트엔드 단위 테스트).

**Spec:** `docs/superpowers/specs/2026-05-05-currency-toggle-design.md`

---

## File Structure

**신규 (백엔드)**
- `tradingagents_web/schemas/fx.py` — `FxRate` Pydantic 모델
- `tradingagents_web/services/fx.py` — yfinance 환율 fetch + 24h TTL 캐시
- `tradingagents_web/api/fx.py` — `/api/fx/usd-krw` 라우트
- `tests/web/test_fx_service.py` — 서비스 단위 테스트
- `tests/web/test_fx_api.py` — 라우트 통합 테스트

**신규 (프론트엔드)**
- `web/lib/fx.ts` — `getUsdKrwRate()` API 클라이언트
- `web/lib/currency.tsx` — `CurrencyProvider`, `useCurrency`, `formatPrice`
- `web/lib/currency.test.cjs` — `formatPrice` 단위 테스트
- `web/hooks/use-fx-rate.ts` — React Query 훅
- `web/components/nav/currency-toggle.tsx` — 세그먼트 토글 UI

**수정**
- `tradingagents_web/main.py` — fx 라우터 등록
- `web/app/(workspace)/layout.tsx` — `CurrencyProvider`로 children 래핑
- `web/components/nav/sidebar.tsx` — 데스크톱 토글 배치
- `web/components/nav/mobile-top-bar.tsx` — 모바일 토글 배치
- `web/components/portfolio/holdings-table.tsx` — `formatPrice` 적용
- `web/components/portfolio/pnl-cell.tsx` — `formatPrice` 적용 (퍼센트는 유지)
- `web/components/portfolio/price-chart.tsx` — Y축 / 툴팁 / ReferenceLine 라벨
- `web/app/(workspace)/portfolio/[ticker]/page.tsx` — 4개 카드 (Avg cost / Last / P&L)
- `web/components/portfolio/holding-form.tsx` — Avg cost 라벨에 `(USD)` 명시

---

### Task 1: Backend FxRate schema

**Files:**
- Create: `tradingagents_web/schemas/fx.py`

- [ ] **Step 1: Write the schema**

```python
"""Pydantic schemas for the FX (foreign exchange) API."""
from datetime import date, datetime

from pydantic import BaseModel


class FxRate(BaseModel):
    """USD/KRW spot rate snapshot.

    rate is None when the upstream lookup failed and no prior cache existed.
    """

    pair: str  # "USDKRW"
    rate: float | None
    as_of: date | None
    fetched_at: datetime
```

- [ ] **Step 2: Verify import works**

Run: `uv run python -c "from tradingagents_web.schemas.fx import FxRate; print(FxRate(pair='USDKRW', rate=1380.0, as_of=None, fetched_at=__import__('datetime').datetime.now()))"`

Expected: prints a model instance without error.

- [ ] **Step 3: Commit**

```bash
git add tradingagents_web/schemas/fx.py
git commit -m "feat(web): add FxRate pydantic schema"
```

---

### Task 2: Backend fx service — happy path with TDD

**Files:**
- Create: `tradingagents_web/services/fx.py`
- Create: `tests/web/test_fx_service.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the FX service (yfinance KRW=X wrapper + 24h TTL cache)."""
import pytest

from tradingagents_web.services import fx as svc


@pytest.fixture(autouse=True)
def _clear_cache():
    svc.clear_cache()
    yield
    svc.clear_cache()


def test_get_rate_returns_last_close(monkeypatch):
    captured = {"calls": 0}

    def fake_download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True):
        captured["calls"] += 1
        import pandas as pd
        idx = pd.to_datetime(["2026-05-04", "2026-05-05"])
        return pd.DataFrame({"Close": [1370.5, 1382.1]}, index=idx)

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    out = svc.get_usd_krw_rate()
    assert out.pair == "USDKRW"
    assert out.rate == 1382.1
    assert out.as_of.isoformat() == "2026-05-05"
    assert captured["calls"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_fx_service.py::test_get_rate_returns_last_close -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'tradingagents_web.services.fx'`.

- [ ] **Step 3: Write minimal implementation**

Create `tradingagents_web/services/fx.py` with exactly this content:

```python
"""yfinance USD/KRW wrapper with a 24-hour TTL cache.

The cache holds at most one entry (single currency pair). yfinance.download
is not thread-safe, so we share services.prices._YF_LOCK rather than taking
a separate lock — taking two locks would let concurrent callers race inside
yfinance's internal globals.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from typing import Any

from tradingagents_web.schemas.fx import FxRate
from tradingagents_web.services.prices import _YF_LOCK

logger = logging.getLogger(__name__)

_TTL_SECONDS = 24 * 3600
_CACHE: tuple[float, FxRate] | None = None


def _yf_download(ticker: str, period: str = "5d", interval: str = "1d") -> Any:
    """Indirection so tests can monkeypatch this module directly.

    yfinance accepts either (start, end) or period; we use period here
    because we just want the last few business days for FX. The shared
    _YF_LOCK from services.prices serializes all yfinance calls in this
    process.
    """
    import yfinance as yf

    with _YF_LOCK:
        return yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )


def _extract_last_close(df: Any) -> tuple[float | None, date | None]:
    """Return (rate, as_of) from a yfinance DataFrame, skipping NaN rows."""
    if df is None or len(df) == 0 or "Close" not in df.columns:
        return None, None
    series = df["Close"].dropna()
    if series.empty:
        return None, None
    last_ts = series.index[-1]
    return float(series.iloc[-1]), last_ts.date()


def get_usd_krw_rate() -> FxRate:
    """USD/KRW spot rate. 24h TTL cache; falls back to stale cache on error."""
    global _CACHE
    now = time.time()
    cached = _CACHE
    if cached and cached[0] > now:
        return cached[1]

    fetched_at = datetime.now(timezone.utc)
    try:
        df = _yf_download("KRW=X")
        rate, as_of = _extract_last_close(df)
        result = FxRate(
            pair="USDKRW", rate=rate, as_of=as_of, fetched_at=fetched_at,
        )
    except Exception:  # noqa: BLE001
        logger.exception("yfinance KRW=X download failed")
        if cached is not None:
            return cached[1]
        result = FxRate(
            pair="USDKRW", rate=None, as_of=None, fetched_at=fetched_at,
        )

    _CACHE = (now + _TTL_SECONDS, result)
    return result


def clear_cache() -> None:
    """Drop the in-memory cache (used by tests)."""
    global _CACHE
    _CACHE = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/web/test_fx_service.py::test_get_rate_returns_last_close -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tradingagents_web/services/fx.py tests/web/test_fx_service.py
git commit -m "feat(web): add fx service with 24h TTL cache (happy path)"
```

---

### Task 3: Backend fx service — cache hit, failures, empty df

**Files:**
- Modify: `tests/web/test_fx_service.py`

- [ ] **Step 1: Add four more failing tests**

Append to `tests/web/test_fx_service.py`:

```python
def test_cache_hit_skips_download(monkeypatch):
    captured = {"calls": 0}

    def fake_download(ticker, period="5d", interval="1d", **kw):
        captured["calls"] += 1
        import pandas as pd
        idx = pd.to_datetime(["2026-05-05"])
        return pd.DataFrame({"Close": [1382.1]}, index=idx)

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    first = svc.get_usd_krw_rate()
    second = svc.get_usd_krw_rate()
    assert first.rate == 1382.1
    assert second.rate == 1382.1
    assert captured["calls"] == 1


def test_yfinance_failure_no_cache_returns_null_rate(monkeypatch):
    def fake_download(*a, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    out = svc.get_usd_krw_rate()
    assert out.rate is None
    assert out.as_of is None
    assert out.pair == "USDKRW"


def test_yfinance_failure_with_prior_cache_returns_stale(monkeypatch):
    # Prime the cache with a successful call.
    def good(ticker, period="5d", interval="1d", **kw):
        import pandas as pd
        idx = pd.to_datetime(["2026-05-05"])
        return pd.DataFrame({"Close": [1382.1]}, index=idx)

    monkeypatch.setattr(svc, "_yf_download", good)
    primed = svc.get_usd_krw_rate()
    assert primed.rate == 1382.1

    # Force the cache to expire so the next call re-downloads, then fail.
    svc._CACHE = (0, primed)

    def boom(*a, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(svc, "_yf_download", boom)

    stale = svc.get_usd_krw_rate()
    assert stale.rate == 1382.1  # served from prior cache despite TTL expiry


def test_empty_dataframe_returns_null_rate(monkeypatch):
    def fake_download(*a, **kw):
        import pandas as pd
        return pd.DataFrame({"Close": []}, index=pd.to_datetime([]))

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    out = svc.get_usd_krw_rate()
    assert out.rate is None
    assert out.as_of is None
```

- [ ] **Step 2: Run all fx service tests**

Run: `uv run pytest tests/web/test_fx_service.py -v`

Expected: All 5 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/web/test_fx_service.py
git commit -m "test(web): cover fx service cache hit, failures, empty df"
```

---

### Task 4: Backend fx API route

**Files:**
- Create: `tradingagents_web/api/fx.py`
- Modify: `tradingagents_web/main.py`
- Create: `tests/web/test_fx_api.py`

- [ ] **Step 1: Write the failing API tests**

Create `tests/web/test_fx_api.py`:

```python
"""API tests for /api/fx."""
from datetime import date, datetime, timezone

from tradingagents_web.auth import create_session
from tradingagents_web.config import Settings
from tradingagents_web.models import User
from tradingagents_web.schemas.fx import FxRate
from tradingagents_web.services import fx as fx_svc

_settings = Settings()


def _login(app_with_test_db, client):
    _, TestSessionLocal = app_with_test_db
    db = TestSessionLocal()
    try:
        user = User(password_hash="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_session(db, user.id)
    finally:
        db.close()
    client.cookies.set(_settings.session_cookie_name, token)
    return client


def test_get_usd_krw(monkeypatch, app_with_test_db, client):
    fake = FxRate(
        pair="USDKRW",
        rate=1382.1,
        as_of=date(2026, 5, 5),
        fetched_at=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(fx_svc, "get_usd_krw_rate", lambda: fake)
    client = _login(app_with_test_db, client)

    r = client.get("/api/fx/usd-krw")
    assert r.status_code == 200
    body = r.json()
    assert body["pair"] == "USDKRW"
    assert body["rate"] == 1382.1
    assert body["as_of"] == "2026-05-05"


def test_get_usd_krw_requires_auth(client):
    r = client.get("/api/fx/usd-krw")
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_fx_api.py -v`

Expected: Both FAIL — likely 404 since the route doesn't exist yet.

- [ ] **Step 3: Implement the route**

Create `tradingagents_web/api/fx.py`:

```python
"""Read-only API for FX (foreign exchange) rates."""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends

from tradingagents_web.auth import get_current_user
from tradingagents_web.models import User
from tradingagents_web.schemas.fx import FxRate
from tradingagents_web.services import fx as fx_svc

router = APIRouter(prefix="/api/fx", tags=["fx"])


@router.get("/usd-krw", response_model=FxRate)
async def usd_krw(
    _user: Annotated[User, Depends(get_current_user)],
) -> FxRate:
    return await asyncio.to_thread(fx_svc.get_usd_krw_rate)
```

- [ ] **Step 4: Register the router**

Modify `tradingagents_web/main.py`:

Find the line:
```python
from tradingagents_web.api import prices as prices_api
```

Add immediately after:
```python
from tradingagents_web.api import fx as fx_api
```

Find the section in `create_app` where routers are registered (after `app.include_router(account_api.router)` and around the other `include_router` calls). Add:
```python
    app.include_router(fx_api.router)
```

(Insert it adjacent to `app.include_router(prices_api.router)` for grouping consistency.)

- [ ] **Step 5: Run API tests to verify they pass**

Run: `uv run pytest tests/web/test_fx_api.py -v`

Expected: Both PASS.

- [ ] **Step 6: Commit**

```bash
git add tradingagents_web/api/fx.py tradingagents_web/main.py tests/web/test_fx_api.py
git commit -m "feat(web): add /api/fx/usd-krw route"
```

---

### Task 5: Frontend FX API client

**Files:**
- Create: `web/lib/fx.ts`

- [ ] **Step 1: Write the client**

```ts
import { api } from "./api";

export interface FxRate {
  pair: "USDKRW";
  rate: number | null;
  as_of: string | null;
  fetched_at: string;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function getUsdKrwRate(): Promise<FxRate> {
  return api(`${BASE}/api/fx/usd-krw`);
}
```

- [ ] **Step 2: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS (no new errors).

- [ ] **Step 3: Commit**

```bash
git add web/lib/fx.ts
git commit -m "feat(web): add fx client (lib/fx.ts)"
```

---

### Task 6: Frontend useFxRate hook

**Files:**
- Create: `web/hooks/use-fx-rate.ts`

- [ ] **Step 1: Write the hook**

```ts
"use client";
import { useQuery } from "@tanstack/react-query";
import { getUsdKrwRate, FxRate } from "@/lib/fx";

const TWELVE_HOURS_MS = 12 * 60 * 60 * 1000;

export function useFxRate() {
  return useQuery<FxRate>({
    queryKey: ["fx", "usd-krw"],
    queryFn: getUsdKrwRate,
    staleTime: TWELVE_HOURS_MS,
    gcTime: TWELVE_HOURS_MS,
    refetchOnWindowFocus: false,
  });
}
```

- [ ] **Step 2: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add web/hooks/use-fx-rate.ts
git commit -m "feat(web): add useFxRate hook (12h staleTime)"
```

---

### Task 7: Frontend formatPrice helper with TDD

**Files:**
- Create: `web/lib/currency.tsx`
- Create: `web/lib/currency.test.cjs`

- [ ] **Step 1: Write the failing tests**

Create `web/lib/currency.test.cjs` (mirrors `web/lib/indicators.test.cjs`):

```js
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const Module = require("node:module");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

function loadTsModule(relativePath) {
  const filename = path.join(__dirname, relativePath);
  const source = readFileSync(filename, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.ReactJSX,
    },
    fileName: filename,
  });
  const mod = new Module(filename, module);
  mod.filename = filename;
  mod.paths = Module._nodeModulePaths(__dirname);
  mod._compile(outputText, filename);
  return mod.exports;
}

test("formatPrice: USD positive default", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(formatPrice(123.45, { currency: "USD", fxRate: null }), "$123.45");
});

test("formatPrice: USD negative places sign before symbol", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(formatPrice(-12.34, { currency: "USD", fxRate: null }), "-$12.34");
});

test("formatPrice: USD signed=true on positive", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(12.34, { currency: "USD", fxRate: null }, { signed: true }),
    "+$12.34",
  );
});

test("formatPrice: KRW with fxRate rounds and adds comma", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  // 123.45 * 1380 = 170361 exactly
  assert.equal(
    formatPrice(123.45, { currency: "KRW", fxRate: 1380 }),
    "₩170,361",
  );
});

test("formatPrice: KRW negative places sign before symbol", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(-100, { currency: "KRW", fxRate: 1380 }),
    "-₩138,000",
  );
});

test("formatPrice: null returns em-dash", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(formatPrice(null, { currency: "USD", fxRate: null }), "—");
  assert.equal(formatPrice(undefined, { currency: "KRW", fxRate: 1380 }), "—");
});

test("formatPrice: usdDecimals option", () => {
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(
    formatPrice(123.45, { currency: "USD", fxRate: null }, { usdDecimals: 0 }),
    "$123",
  );
});

test("formatPrice: KRW with null fxRate falls back to USD", () => {
  // The Provider routes effectiveCurrency to "USD" when fxRate is null,
  // but formatPrice should also be defensive: if currency is "KRW" but
  // fxRate is null, render USD format.
  const { formatPrice } = loadTsModule("currency.tsx");
  assert.equal(formatPrice(50, { currency: "KRW", fxRate: null }), "$50.00");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `web/`: `node --test lib/currency.test.cjs`

Expected: All FAIL — `currency.tsx` does not exist yet.

- [ ] **Step 3: Implement formatPrice + Provider + hook in currency.tsx**

Create `web/lib/currency.tsx`:

```tsx
"use client";
import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useFxRate } from "@/hooks/use-fx-rate";

export type Currency = "USD" | "KRW";

export interface CurrencyCtx {
  currency: Currency;
  setCurrency: (c: Currency) => void;
  toggle: () => void;
  fxRate: number | null;
  fxAsOf: string | null;
  fxLoading: boolean;
}

const STORAGE_KEY = "currency-preference";

const CurrencyContext = createContext<CurrencyCtx | null>(null);

function readSaved(): Currency {
  if (typeof window === "undefined") return "USD";
  const saved = window.localStorage.getItem(STORAGE_KEY);
  return saved === "USD" || saved === "KRW" ? saved : "USD";
}

export function CurrencyProvider({ children }: { children: ReactNode }) {
  // First render is always "USD" to avoid SSR/hydration mismatch.
  const [currency, setCurrencyState] = useState<Currency>("USD");
  const { data, isLoading } = useFxRate();

  useEffect(() => {
    setCurrencyState(readSaved());
  }, []);

  const setCurrency = useCallback((c: Currency) => {
    setCurrencyState(c);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, c);
    }
  }, []);

  const fxRate = data?.rate ?? null;
  const effective: Currency = currency === "KRW" && fxRate == null ? "USD" : currency;

  const toggle = useCallback(() => {
    setCurrency(effective === "USD" ? "KRW" : "USD");
  }, [effective, setCurrency]);

  const value: CurrencyCtx = {
    currency: effective,
    setCurrency,
    toggle,
    fxRate,
    fxAsOf: data?.as_of ?? null,
    fxLoading: isLoading,
  };

  return (
    <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>
  );
}

export function useCurrency(): CurrencyCtx {
  const ctx = useContext(CurrencyContext);
  if (!ctx) {
    throw new Error("useCurrency must be used inside <CurrencyProvider>");
  }
  return ctx;
}

export function formatPrice(
  usdValue: number | null | undefined,
  ctx: Pick<CurrencyCtx, "currency" | "fxRate">,
  opts?: { signed?: boolean; usdDecimals?: number },
): string {
  if (usdValue == null || !Number.isFinite(usdValue)) return "—";

  const isNeg = usdValue < 0;
  const abs = Math.abs(usdValue);
  const signPrefix = isNeg ? "-" : opts?.signed ? "+" : "";

  if (ctx.currency === "KRW" && ctx.fxRate != null) {
    const krw = Math.round(abs * ctx.fxRate);
    return `${signPrefix}₩${krw.toLocaleString()}`;
  }

  const decimals = opts?.usdDecimals ?? 2;
  return `${signPrefix}$${abs.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run from `web/`: `node --test lib/currency.test.cjs`

Expected: All 8 tests PASS.

- [ ] **Step 5: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/lib/currency.tsx web/lib/currency.test.cjs
git commit -m "feat(web): add CurrencyProvider, useCurrency, formatPrice"
```

---

### Task 8: Currency toggle UI component

**Files:**
- Create: `web/components/nav/currency-toggle.tsx`

- [ ] **Step 1: Write the component**

```tsx
"use client";
import { useCurrency } from "@/lib/currency";
import { cn } from "@/lib/utils";

/**
 * Segmented USD/KRW toggle. Renders compact (icon-sized) or wide (with
 * `as_of` footnote) depending on the `compact` prop.
 *
 * KRW button is disabled when fxRate is unavailable.
 */
export function CurrencyToggle({ compact = false }: { compact?: boolean }) {
  const { currency, setCurrency, fxRate, fxAsOf } = useCurrency();
  const krwDisabled = fxRate == null;

  const btn = (active: boolean, disabled: boolean) =>
    cn(
      "px-2 py-1 text-[11px] font-semibold tracking-[-0.01em] transition-colors rounded-md",
      active
        ? "bg-text-1 text-bg-1"
        : disabled
        ? "text-text-3/40 cursor-not-allowed"
        : "text-text-3 hover:text-text-1",
    );

  return (
    <div className="flex flex-col items-end gap-0.5">
      <div
        role="group"
        aria-label="표시 통화 선택"
        className="inline-flex items-center gap-0.5 rounded-lg border border-border-1 bg-bg-1 p-0.5"
      >
        <button
          type="button"
          className={btn(currency === "USD", false)}
          onClick={() => setCurrency("USD")}
          aria-pressed={currency === "USD"}
        >
          USD
        </button>
        <button
          type="button"
          className={btn(currency === "KRW", krwDisabled)}
          onClick={() => !krwDisabled && setCurrency("KRW")}
          disabled={krwDisabled}
          aria-pressed={currency === "KRW"}
          title={
            krwDisabled
              ? "환율 정보를 불러올 수 없어 KRW 모드를 사용할 수 없습니다"
              : undefined
          }
        >
          KRW
        </button>
      </div>
      {!compact && currency === "KRW" && fxAsOf && (
        <span className="text-[10px] font-mono text-text-3">as of {fxAsOf}</span>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add web/components/nav/currency-toggle.tsx
git commit -m "feat(web): add CurrencyToggle segmented control"
```

---

### Task 9: Wire CurrencyProvider into workspace layout

**Files:**
- Modify: `web/app/(workspace)/layout.tsx`

- [ ] **Step 1: Update the layout to wrap children**

Replace the contents of `web/app/(workspace)/layout.tsx` with:

```tsx
import { UnreadBell } from "@/components/alerts/unread-bell";
import { Sidebar } from "@/components/nav/sidebar";
import { TabBar } from "@/components/nav/tab-bar";
import { MobileTopBar } from "@/components/nav/mobile-top-bar";
import { RunningRunsIndicator } from "@/components/run/running-runs-indicator";
import { CurrencyProvider } from "@/lib/currency";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <CurrencyProvider>
      <div className="flex min-h-screen bg-bg-0">
        <Sidebar />
        <main className="flex-1 flex flex-col pb-[calc(72px+env(safe-area-inset-bottom))] md:pb-0">
          <MobileTopBar />
          <header className="hidden md:flex sticky top-0 z-20 items-center justify-end gap-2 px-8 py-3 bg-bg-0/80 backdrop-blur supports-[backdrop-filter]:bg-bg-0/70">
            <RunningRunsIndicator />
            <UnreadBell />
          </header>
          <div className="flex-1">{children}</div>
        </main>
        <TabBar />
      </div>
    </CurrencyProvider>
  );
}
```

- [ ] **Step 2: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add web/app/(workspace)/layout.tsx
git commit -m "feat(web): wrap workspace in CurrencyProvider"
```

---

### Task 10: Place toggle in desktop sidebar

**Files:**
- Modify: `web/components/nav/sidebar.tsx`

- [ ] **Step 1: Add the import**

In `web/components/nav/sidebar.tsx`, add this line after the existing `import { Logo } from "@/components/shared/logo";` line:

```tsx
import { CurrencyToggle } from "@/components/nav/currency-toggle";
```

- [ ] **Step 2: Insert the toggle block before `</aside>`**

Find the closing `</nav>` tag (the only one in this file). Immediately after it, before `</aside>`, insert this block:

```tsx
      <div className="mt-auto px-3 pt-4">
        <div className="text-[11px] font-semibold tracking-[-0.01em] text-text-3 pb-1.5">
          표시 통화
        </div>
        <CurrencyToggle />
      </div>
```

The aside already uses `flex flex-col`, so `mt-auto` on this wrapper pushes the toggle to the bottom of the column. The existing `</nav>` and `</aside>` markup is unchanged.

- [ ] **Step 3: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 4: Smoke test in browser**

Run from `web/`: `npm run dev`

Open http://localhost:3000 → log in → check that the sidebar shows a USD/KRW toggle at the bottom on desktop. Click KRW → no errors in console; toggle visual state changes. Reload → choice persists.

Stop the dev server.

- [ ] **Step 5: Commit**

```bash
git add web/components/nav/sidebar.tsx
git commit -m "feat(web): place currency toggle in desktop sidebar"
```

---

### Task 11: Place toggle in mobile top bar

**Files:**
- Modify: `web/components/nav/mobile-top-bar.tsx`

- [ ] **Step 1: Add CurrencyToggle next to UnreadBell**

In `web/components/nav/mobile-top-bar.tsx`, modify the import block — add:

```tsx
import { CurrencyToggle } from "@/components/nav/currency-toggle";
```

Then change the right-hand side of the header from:

```tsx
      <UnreadBell />
    </header>
```

to:

```tsx
      <div className="flex items-center gap-2">
        <CurrencyToggle compact />
        <UnreadBell />
      </div>
    </header>
```

- [ ] **Step 2: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add web/components/nav/mobile-top-bar.tsx
git commit -m "feat(web): place currency toggle in mobile top bar"
```

---

### Task 12: Apply formatPrice in holdings table

**Files:**
- Modify: `web/components/portfolio/holdings-table.tsx`

- [ ] **Step 1: Replace direct toFixed calls with formatPrice**

Replace the contents of `web/components/portfolio/holdings-table.tsx` with:

```tsx
"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Holding } from "@/lib/holdings";
import { useDeleteHolding } from "@/hooks/use-holdings";
import { useCurrency, formatPrice } from "@/lib/currency";
import { MonitorToggle } from "./monitor-toggle";
import { PnLCell } from "./pnl-cell";

export function HoldingsTable({
  rows,
  prices,
}: {
  rows: Holding[];
  prices: Record<string, number | null>;
}) {
  const del = useDeleteHolding();
  const ctx = useCurrency();
  if (rows.length === 0) {
    return (
      <p className="text-sm text-text-3 py-8 text-center">
        No holdings yet — add a ticker above.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-2xs uppercase tracking-wider text-text-3 border-b border-border-1">
            <th className="text-left py-2">Ticker</th>
            <th className="text-right">Qty</th>
            <th className="text-right">Avg Cost</th>
            <th className="text-right">Last</th>
            <th className="text-right">P&amp;L</th>
            <th className="text-center">Monitor</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => {
            const last = prices[h.ticker] ?? null;
            return (
              <tr key={h.id} className="border-b border-border-1 hover:bg-bg-2">
                <td className="py-2 font-mono">
                  <Link className="hover:underline" href={`/portfolio/${h.ticker}`}>
                    {h.ticker}
                  </Link>
                </td>
                <td className="text-right font-mono tabular-nums">{h.qty}</td>
                <td className="text-right font-mono tabular-nums">
                  {formatPrice(h.avg_cost, ctx)}
                </td>
                <td className="text-right font-mono tabular-nums">
                  {formatPrice(last, ctx)}
                </td>
                <td className="text-right">
                  <PnLCell qty={h.qty} avgCost={h.avg_cost} lastPrice={last} />
                </td>
                <td className="text-center">
                  <MonitorToggle holdingId={h.id} enabled={h.monitor_enabled} />
                </td>
                <td className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={del.isPending}
                    onClick={() => del.mutate(h.id)}
                  >
                    Remove
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add web/components/portfolio/holdings-table.tsx
git commit -m "feat(web): use formatPrice in holdings table"
```

---

### Task 13: Apply formatPrice in PnL cell

**Files:**
- Modify: `web/components/portfolio/pnl-cell.tsx`

- [ ] **Step 1: Replace pnl.toFixed with formatPrice**

Replace the contents of `web/components/portfolio/pnl-cell.tsx` with:

```tsx
"use client";
import { useCurrency, formatPrice } from "@/lib/currency";
import { cn } from "@/lib/utils";

export function PnLCell({
  qty,
  avgCost,
  lastPrice,
}: {
  qty: number;
  avgCost: number;
  lastPrice: number | null;
}) {
  const ctx = useCurrency();
  if (lastPrice == null)
    return <span className="text-text-3 font-mono text-xs">—</span>;
  const cost = qty * avgCost;
  const value = qty * lastPrice;
  const pnl = value - cost;
  const pct = cost > 0 ? (pnl / cost) * 100 : 0;
  const cls = pnl >= 0 ? "text-pos" : "text-neg";
  return (
    <span className={cn("font-mono text-xs tabular-nums", cls)}>
      {formatPrice(pnl, ctx, { signed: true })} ({pct >= 0 ? "+" : ""}
      {pct.toFixed(1)}%)
    </span>
  );
}
```

- [ ] **Step 2: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add web/components/portfolio/pnl-cell.tsx
git commit -m "feat(web): use formatPrice in PnL cell"
```

---

### Task 14: Apply formatPrice in portfolio detail page

**Files:**
- Modify: `web/app/(workspace)/portfolio/[ticker]/page.tsx`

- [ ] **Step 1: Add useCurrency import**

In `web/app/(workspace)/portfolio/[ticker]/page.tsx`, add this import after the existing `@/components/shared/signal-badge` import:

```tsx
import { useCurrency, formatPrice } from "@/lib/currency";
```

- [ ] **Step 2: Use the hook in the component**

In the `PortfolioDetail` component body, after `const { settings, setSettings, reset } = useChartSettings();`, add:

```tsx
  const ctx = useCurrency();
```

- [ ] **Step 3: Replace toFixed in the four card values**

Replace the four card cells (Quantity stays as-is — it's a count, not money):

For **Avg cost**, change:
```tsx
              <div className="font-mono tabular-nums">
                {holding.avg_cost.toFixed(2)}
              </div>
```
to:
```tsx
              <div className="font-mono tabular-nums">
                {formatPrice(holding.avg_cost, ctx)}
              </div>
```

For **Last**, change:
```tsx
              <div className="font-mono tabular-nums">
                {last != null ? last.toFixed(2) : "—"}
              </div>
```
to:
```tsx
              <div className="font-mono tabular-nums">
                {formatPrice(last, ctx)}
              </div>
```

For **P&L**, change:
```tsx
              <div
                className={`font-mono tabular-nums ${
                  pnl == null ? "" : pnl >= 0 ? "text-pos" : "text-neg"
                }`}
              >
                {pnl == null ? "—" : `${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}`}
              </div>
```
to:
```tsx
              <div
                className={`font-mono tabular-nums ${
                  pnl == null ? "" : pnl >= 0 ? "text-pos" : "text-neg"
                }`}
              >
                {formatPrice(pnl, ctx, { signed: true })}
              </div>
```

- [ ] **Step 4: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(workspace)/portfolio/[ticker]/page.tsx"
git commit -m "feat(web): use formatPrice in portfolio detail cards"
```

---

### Task 15: Apply formatPrice in price chart

**Files:**
- Modify: `web/components/portfolio/price-chart.tsx`

- [ ] **Step 1: Add useCurrency import**

In `web/components/portfolio/price-chart.tsx`, add this import after the existing `@/components/portfolio/indicator-colors` import:

```tsx
import { useCurrency, formatPrice, type CurrencyCtx } from "@/lib/currency";
```

- [ ] **Step 2: Replace the standalone fmtPrice helper**

Find the existing helper:
```tsx
const fmtPrice = (n: number | null | undefined) =>
  n == null || !Number.isFinite(n)
    ? "—"
    : n.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
```

Replace it with a currency-aware version that takes ctx:
```tsx
function fmtPriceCtx(
  n: number | null | undefined,
  ctx: Pick<CurrencyCtx, "currency" | "fxRate">,
): string {
  return formatPrice(n, ctx);
}
```

- [ ] **Step 3: Pass ctx into PriceTooltip**

Change the `PriceTooltip` signature to accept ctx:

```tsx
function PriceTooltip({
  active,
  payload,
  label,
  signalsByDate,
  ctx,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string | number;
  signalsByDate: Map<string, SignalMarker>;
  ctx: Pick<CurrencyCtx, "currency" | "fxRate">;
}) {
```

Inside the tooltip, change:
```tsx
              <span className="tabular-nums text-text-1">{fmtPrice(value)}</span>
```
to:
```tsx
              <span className="tabular-nums text-text-1">{fmtPriceCtx(value, ctx)}</span>
```

- [ ] **Step 4: Use the hook in PriceChart and pass ctx down**

In the `PriceChart` component body, immediately after the function signature opening brace, add:

```tsx
  const ctx = useCurrency();
```

Then update the Tooltip render:
```tsx
          <Tooltip
            cursor={{ stroke: CHART_CHROME.axis, strokeDasharray: "3 3" }}
            content={
              <PriceTooltip signalsByDate={signalsByDate} ctx={ctx} />
            }
          />
```

Update the YAxis tickFormatter:
```tsx
          <YAxis
            stroke={CHART_CHROME.axis}
            fontSize={10}
            tick={{ fill: CHART_CHROME.tick }}
            width={48}
            domain={["auto", "auto"]}
            tickFormatter={(v) =>
              typeof v === "number" ? formatPrice(v, ctx, { usdDecimals: 0 }) : String(v)
            }
          />
```

(The `usdDecimals: 0` keeps Y-axis labels compact in USD; KRW already integer-rounds.)

Update the avg-cost ReferenceLine label:
```tsx
          {avgCost != null && (
            <ReferenceLine
              y={avgCost}
              stroke={INDICATOR_COLORS.avgCost}
              strokeDasharray="4 3"
              label={{
                value: `Avg ${fmtPriceCtx(avgCost, ctx)}`,
                position: "insideTopRight",
                fill: INDICATOR_COLORS.avgCost,
                fontSize: 10,
              }}
            />
          )}
```

- [ ] **Step 5: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 6: Smoke test in browser**

Run from `web/`: `npm run dev`

Open http://localhost:3000 → log in → navigate to a portfolio detail page (e.g., `/portfolio/AAPL` if you have the holding). Verify:
- Y-axis labels show `$` prefix in USD mode.
- Tooltip shows `$xxx.xx` per series.
- Toggle to KRW → all values become `₩` prefixed integers, axis updates instantly without re-fetching prices (network tab check).

Stop the dev server.

- [ ] **Step 7: Commit**

```bash
git add web/components/portfolio/price-chart.tsx
git commit -m "feat(web): currency-aware price chart axis/tooltip/ref-line"
```

---

### Task 16: Annotate holding form input as USD

**Files:**
- Modify: `web/components/portfolio/holding-form.tsx`

- [ ] **Step 1: Update the Avg cost label**

In `web/components/portfolio/holding-form.tsx`, change:

```tsx
        <Label htmlFor="avg">Avg cost</Label>
```

to:

```tsx
        <Label htmlFor="avg">Avg cost (USD)</Label>
```

- [ ] **Step 2: Verify type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add web/components/portfolio/holding-form.tsx
git commit -m "feat(web): clarify avg cost input is USD"
```

---

### Task 17: Final verification

- [ ] **Step 1: Run all backend tests**

Run from project root: `uv run pytest tests/web/test_fx_service.py tests/web/test_fx_api.py tests/web/test_prices_service.py tests/web/test_prices_api.py -v`

Expected: All PASS.

- [ ] **Step 2: Run frontend unit tests**

Run from `web/`: `node --test lib/currency.test.cjs lib/indicators.test.cjs lib/sse-url.test.cjs`

Expected: All PASS.

- [ ] **Step 3: Final type-check**

Run from `web/`: `npm run typecheck`

Expected: PASS.

- [ ] **Step 4: End-to-end smoke test**

Run from project root: `./dev.sh` (or equivalent — start both API and web).

In the browser:
1. Log in.
2. Confirm sidebar shows USD/KRW toggle (desktop) and mobile top bar shows compact toggle (responsive view).
3. Navigate to `/portfolio` — Avg Cost / Last / P&L all show `$` prefix.
4. Click KRW on the toggle — all values switch to `₩` integer format. Network tab shows `/api/fx/usd-krw` was called once at load (or on first toggle in dev mode), not on each toggle.
5. Reload — KRW selection persists.
6. Navigate to a portfolio detail page — chart Y-axis, tooltip, avg-cost reference line all show in selected currency.
7. Click USD — instant rollback.

Stop the servers.

- [ ] **Step 5: Final commit (if any cleanup)**

If the smoke test surfaced cosmetic fixes, commit them with descriptive messages. Otherwise this task closes the feature.
