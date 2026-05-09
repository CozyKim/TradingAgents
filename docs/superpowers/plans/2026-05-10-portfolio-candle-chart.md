# 포트폴리오 캔들 차트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/portfolio/[ticker]` 화면의 Recharts 라인차트를 TradingView Lightweight Charts 기반 캔들+거래량+보조지표 차트로 교체한다.

**Architecture:** 백엔드는 yfinance가 이미 주는 OHLCV 전체를 `PricePoint`에 펴서 노출한다(NaN/inf 행 스킵, MultiIndex 방어). 프론트는 백엔드에서 받은 일봉을 프론트에서 주/월로 리샘플링하고, 같은 `bucketKey`를 신호 마커에도 적용해 인터벌 전환에서 마커가 어긋나지 않게 한다. 보조지표(EMA/Bollinger/RSI/Stoch)는 기존 `useChartSettings` 훅과 `IndicatorToolbar` UI를 그대로 재사용하되, `series-builder.ts`라는 어댑터가 ChartSettings를 Lightweight Charts pane/series로 매핑한다.

**Tech Stack:** Python 3.10+ / FastAPI / Pydantic v2 / pandas / yfinance · Next.js 14 / React 18 / TypeScript / Lightweight Charts v5 / date-fns / Vitest / Playwright

**Spec:** [`docs/superpowers/specs/2026-05-10-portfolio-candle-chart-design.md`](../specs/2026-05-10-portfolio-candle-chart-design.md)

---

## Backend Files

| Path | 변경 |
|---|---|
| `tradingagents_web/schemas/price.py` | `PricePoint`에 open/high/low/volume 필드 추가 |
| `tradingagents_web/services/prices.py` | `_select_ticker_ohlcv` + `_row_is_valid` 헬퍼 추가, 메인 루프 OHLCV로 확장 |
| `tests/web/test_prices_service.py` | OHLCV 픽스처로 갱신, NaN/MultiIndex 회귀 추가 |
| `tests/web/test_prices_api.py` | PricePoint 생성자 갱신 |

## Frontend Files

| Path | 변경 |
|---|---|
| `web/package.json` | `lightweight-charts`, `date-fns`, `vitest`, `@vitejs/plugin-react`, `jsdom` 추가 |
| `web/vitest.config.ts` | 신규 — 단위 테스트 설정 |
| `web/lib/prices.ts` | `PricePoint`에 OHLCV 필드 추가 |
| `web/components/portfolio/candle-chart/resample.ts` | 신규 — `bucketKey`, `resample`, `alignSignals` |
| `web/components/portfolio/candle-chart/series-config.ts` | 신규 — 색상 상수 |
| `web/components/portfolio/candle-chart/series-builder.ts` | 신규 — ChartSettings ↔ Lightweight Charts series 어댑터 |
| `web/components/portfolio/candle-chart/ohlc-header.tsx` | 신규 — 시가/고가/저가/종가/% 표시 |
| `web/components/portfolio/candle-chart/interval-tabs.tsx` | 신규 — 일/주/월 탭 |
| `web/components/portfolio/candle-chart/candle-chart.tsx` | 신규 — 메인 차트 컴포넌트 |
| `web/components/portfolio/candle-chart/index.ts` | 신규 — 외부 export |
| `web/components/portfolio/__tests__/resample.test.ts` | 신규 — `bucketKey`/`resample`/`alignSignals` 단위 테스트 |
| `web/app/(workspace)/portfolio/[ticker]/page.tsx` | `<ChartStack>` → `<CandleChart>`, days 90→365 |
| `web/components/portfolio/price-chart.tsx` | 삭제 |
| `web/components/portfolio/chart-stack.tsx` | 삭제 |
| `web/components/portfolio/indicator-panel.tsx` | 삭제 |
| `web/tests/e2e/portfolio.spec.ts` | 신규 — 인터벌 탭 + 보조지표 토글 E2E |

---

## Task 1: Backend — `PricePoint` 스키마 확장

**Files:**
- Modify: `tradingagents_web/schemas/price.py`
- Test: `tests/web/test_prices_api.py`(픽스처 갱신)

- [ ] **Step 1: 기존 픽스처를 새 스키마로 갱신해 실패 확인**

`tests/web/test_prices_api.py:31`을 수정 — 새 필드를 채우는 픽스처:

```python
from datetime import date

# test_get_price_history 안의 fake 생성 부분
fake = PriceHistoryResponse(
    ticker="AAPL",
    points=[
        PricePoint(
            date=date(2026, 4, 22),
            open=180.0,
            high=182.5,
            low=179.4,
            close=181.5,
            volume=12_345_678,
        ),
    ],
    last_close=181.5,
)
```

- [ ] **Step 2: 테스트 실행으로 실패 확인**

```bash
pytest tests/web/test_prices_api.py::test_get_price_history -v
```

Expected: FAIL — `PricePoint` 생성 시 unexpected keyword arguments 또는 validation error.

- [ ] **Step 3: `PricePoint` 스키마 확장**

`tradingagents_web/schemas/price.py`를 다음으로 교체:

```python
"""Pydantic schemas for the prices API."""
from datetime import date

from pydantic import BaseModel


class PricePoint(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceHistoryResponse(BaseModel):
    ticker: str
    points: list[PricePoint]
    last_close: float | None
```

- [ ] **Step 4: 테스트 실행으로 통과 확인**

```bash
pytest tests/web/test_prices_api.py -v
```

Expected: 두 테스트 모두 PASS. (기존 service 테스트는 다음 Task에서 손본다.)

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/schemas/price.py tests/web/test_prices_api.py
git commit -m "feat(prices): PricePoint에 OHLCV 필드 추가

캔들 차트가 사용할 시·고·저가·거래량을 응답에 포함시키기 위한 첫 단계.
서비스 레이어는 다음 커밋에서 갱신한다."
```

---

## Task 2: Backend — `_select_ticker_ohlcv` 헬퍼 (TDD)

**Files:**
- Modify: `tradingagents_web/services/prices.py`
- Test: `tests/web/test_prices_service.py`

- [ ] **Step 1: 실패 테스트 추가**

`tests/web/test_prices_service.py` 끝에 추가:

```python
import pandas as pd
from tradingagents_web.services.prices import _select_ticker_ohlcv


def _flat_ohlcv_frame() -> pd.DataFrame:
    idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
    return pd.DataFrame(
        {
            "Open": [180.0, 181.0],
            "High": [182.5, 183.2],
            "Low": [179.4, 180.6],
            "Close": [181.5, 182.7],
            "Volume": [12_345_678, 9_876_543],
        },
        index=idx,
    )


def _multi_ohlcv_frame(tickers: list[str]) -> pd.DataFrame:
    """yfinance MultiIndex shape: columns are (field, ticker)."""
    idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
    fields = ["Open", "High", "Low", "Close", "Volume"]
    cols = pd.MultiIndex.from_product([fields, tickers])
    # 각 ticker 별로 다른 값을 채워 교차오염 시 검출 가능하게 한다.
    data = {}
    for f in fields:
        for t in tickers:
            base = 100.0 if t == "AAPL" else 200.0
            offset = {"Open": 0, "High": 2, "Low": -1, "Close": 1, "Volume": 1_000}[f]
            data[(f, t)] = [base + offset, base + offset + 0.5]
    return pd.DataFrame(data, index=idx, columns=cols)


def test_select_flat_frame_returns_ohlcv_columns():
    df = _flat_ohlcv_frame()
    out = _select_ticker_ohlcv(df, "AAPL")
    assert out is not None
    assert list(out.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert list(out["Close"]) == [181.5, 182.7]


def test_select_multiindex_frame_picks_requested_ticker():
    df = _multi_ohlcv_frame(["NFLX", "AAPL"])
    out = _select_ticker_ohlcv(df, "AAPL")
    assert out is not None
    # AAPL base=100, Close offset=+1 → [101.0, 101.5]
    assert list(out["Close"]) == [101.0, 101.5]


def test_select_multiindex_frame_drops_when_ticker_missing():
    df = _multi_ohlcv_frame(["NFLX", "GOOGL"])
    assert _select_ticker_ohlcv(df, "AAPL") is None


def test_select_returns_none_for_empty_frame():
    assert _select_ticker_ohlcv(pd.DataFrame(), "AAPL") is None
    assert _select_ticker_ohlcv(None, "AAPL") is None  # type: ignore[arg-type]


def test_select_flat_frame_with_partial_columns_returns_none():
    """Open/Close만 있고 High/Low/Volume이 없으면 안전하게 폐기."""
    idx = pd.to_datetime(["2026-04-21"])
    df = pd.DataFrame({"Open": [1.0], "Close": [2.0]}, index=idx)
    assert _select_ticker_ohlcv(df, "AAPL") is None
```

- [ ] **Step 2: 테스트 실행으로 실패 확인**

```bash
pytest tests/web/test_prices_service.py -v -k select_
```

Expected: FAIL with `ImportError: cannot import name '_select_ticker_ohlcv'`.

- [ ] **Step 3: 헬퍼 구현 추가**

`tradingagents_web/services/prices.py`의 import 블록 아래(line 18 부근, `logger = ...` 다음) + 헬퍼 추가:

```python
import math

import pandas as pd

OHLCV_FIELDS: tuple[str, ...] = ("Open", "High", "Low", "Close", "Volume")


def _select_ticker_ohlcv(
    df: "pd.DataFrame | None", ticker: str
) -> "pd.DataFrame | None":
    """Return a flat OHLCV frame for ``ticker``, or None if unrecoverable.

    Handles two yfinance return shapes:
      - flat columns: ["Open","High","Low","Close","Volume"]
      - MultiIndex columns: [(field, ticker), ...]

    Defense-in-depth against ``multi_level_index=False`` being silently
    ignored or against multi-ticker frames leaking past the YF lock.
    """
    if df is None or len(df) == 0:
        return None

    # Case 1: flat columns. Require the full OHLCV set.
    if all(f in df.columns for f in OHLCV_FIELDS):
        out = df
        for f in OHLCV_FIELDS:
            col = out[f]
            if hasattr(col, "columns"):  # accessor returned a DataFrame
                if ticker in col.columns:
                    out = out.assign(**{f: col[ticker]})
                else:
                    logger.warning(
                        "prices: %s missing from %s column for %s; aborting",
                        ticker, f, list(col.columns),
                    )
                    return None
        return out[list(OHLCV_FIELDS)]

    # Case 2: MultiIndex (field, ticker).
    if isinstance(df.columns, pd.MultiIndex):
        try:
            sub = df.xs(ticker, axis=1, level=1, drop_level=True)
        except KeyError:
            logger.warning("prices: ticker %s not in MultiIndex frame", ticker)
            return None
        if not all(f in sub.columns for f in OHLCV_FIELDS):
            return None
        return sub[list(OHLCV_FIELDS)]

    return None
```

- [ ] **Step 4: 테스트 실행으로 통과 확인**

```bash
pytest tests/web/test_prices_service.py -v -k select_
```

Expected: 5개 테스트 모두 PASS.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/prices.py tests/web/test_prices_service.py
git commit -m "feat(prices): MultiIndex 방어 _select_ticker_ohlcv 헬퍼 추가

flat / MultiIndex / 누락 / 빈 프레임 4가지 경로를 결정론적으로 처리.
다음 커밋에서 메인 루프에 연결한다."
```

---

## Task 3: Backend — `_row_is_valid` + 메인 루프 OHLCV 확장 (TDD)

**Files:**
- Modify: `tradingagents_web/services/prices.py`
- Test: `tests/web/test_prices_service.py`

- [ ] **Step 1: 실패 테스트 추가**

`tests/web/test_prices_service.py`에 추가:

```python
import math

import numpy as np


def test_get_history_returns_ohlcv_points(monkeypatch):
    def fake(*a, **kw):
        return _flat_ohlcv_frame()

    monkeypatch.setattr(svc, "_yf_download", fake)
    out = svc.get_price_history("AAPL", days=5)
    assert len(out.points) == 2
    p0 = out.points[0]
    assert p0.open == 180.0
    assert p0.high == 182.5
    assert p0.low == 179.4
    assert p0.close == 181.5
    assert p0.volume == 12_345_678
    assert out.last_close == 182.7  # 마지막 close


def test_get_history_skips_rows_with_nan_ohlc(monkeypatch):
    def fake(*a, **kw):
        idx = pd.to_datetime(["2026-04-21", "2026-04-22", "2026-04-23"])
        return pd.DataFrame(
            {
                "Open":   [180.0, math.nan, 182.0],
                "High":   [182.0, 183.0,   184.0],
                "Low":    [179.0, 180.0,   181.0],
                "Close":  [181.0, 182.0,   183.0],
                "Volume": [10,    20,      30],
            },
            index=idx,
        )

    monkeypatch.setattr(svc, "_yf_download", fake)
    out = svc.get_price_history("AAPL", days=5)
    # NaN Open 행은 통째로 스킵 → 2개만 남는다.
    assert len(out.points) == 2
    assert [p.open for p in out.points] == [180.0, 182.0]
    # last_close는 마지막 valid 행 기준.
    assert out.last_close == 183.0


def test_get_history_skips_inf_close(monkeypatch):
    def fake(*a, **kw):
        idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
        return pd.DataFrame(
            {
                "Open":   [180.0, 181.0],
                "High":   [182.0, 183.0],
                "Low":    [179.0, 180.0],
                "Close":  [181.0, math.inf],
                "Volume": [10,    20],
            },
            index=idx,
        )

    monkeypatch.setattr(svc, "_yf_download", fake)
    out = svc.get_price_history("AAPL", days=5)
    assert len(out.points) == 1
    assert out.last_close == 181.0


def test_get_history_volume_nan_normalized_to_zero(monkeypatch):
    def fake(*a, **kw):
        idx = pd.to_datetime(["2026-04-21"])
        return pd.DataFrame(
            {
                "Open":   [180.0],
                "High":   [182.0],
                "Low":    [179.0],
                "Close":  [181.0],
                "Volume": [math.nan],
            },
            index=idx,
        )

    monkeypatch.setattr(svc, "_yf_download", fake)
    out = svc.get_price_history("XYZ", days=5)
    assert len(out.points) == 1
    assert out.points[0].volume == 0


def test_get_history_all_invalid_rows_returns_empty(monkeypatch):
    def fake(*a, **kw):
        idx = pd.to_datetime(["2026-04-21"])
        return pd.DataFrame(
            {
                "Open":   [math.nan],
                "High":   [math.nan],
                "Low":    [math.nan],
                "Close":  [math.nan],
                "Volume": [0],
            },
            index=idx,
        )

    monkeypatch.setattr(svc, "_yf_download", fake)
    out = svc.get_price_history("XYZ", days=5)
    assert out.points == []
    assert out.last_close is None
```

- [ ] **Step 2: 테스트 실행으로 실패 확인**

```bash
pytest tests/web/test_prices_service.py -v -k "ohlcv_points or nan_ohlc or inf_close or volume_nan or all_invalid"
```

Expected: FAIL — 기존 메인 루프가 `Close`만 추출하므로 `p0.open` 어트리뷰트는 존재하더라도 0.0이 되거나 stale 픽스처와 충돌.

- [ ] **Step 3: `_row_is_valid` + 메인 루프 OHLCV 확장**

`tradingagents_web/services/prices.py`의 `_select_ticker_ohlcv` 아래에 추가:

```python
def _row_is_valid(row: "pd.Series") -> bool:
    """All OHLC fields must be finite. Volume may be NaN (treated as 0)."""
    for f in ("Open", "High", "Low", "Close"):
        v = row[f]
        if not pd.notna(v):
            return False
        try:
            if not math.isfinite(float(v)):
                return False
        except (TypeError, ValueError):
            return False
    return True
```

이어서 `get_price_history`의 본문 중 `points: list[PricePoint] = []` 이후 yfinance 결과를 처리하는 블록 전체(line 80~100 부근, `if df is not None and len(df) > 0 and "Close" in df.columns:` ~ `last_close = points[-1].close if points else None`)를 다음으로 교체:

```python
    sub = _select_ticker_ohlcv(df, key[0])
    if sub is not None:
        for ts, row in sub.iterrows():
            if not _row_is_valid(row):
                continue
            vol_raw = row["Volume"]
            try:
                vol_finite = pd.notna(vol_raw) and math.isfinite(float(vol_raw))
            except (TypeError, ValueError):
                vol_finite = False
            volume = int(float(vol_raw)) if vol_finite else 0
            points.append(PricePoint(
                date=ts.date(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=volume,
            ))
        last_close = points[-1].close if points else None
```

- [ ] **Step 4: 테스트 실행으로 통과 확인**

```bash
pytest tests/web/test_prices_service.py -v
```

Expected: 새 테스트 5개 PASS. **기존 테스트는 일부 실패할 수 있음** — `test_get_history_returns_points`는 `Close`만 있는 픽스처를 쓰므로 새 검증 로직이 행을 통째로 스킵한다. Task 4에서 픽스처를 갱신한다.

- [ ] **Step 5: 커밋**

```bash
git add tradingagents_web/services/prices.py tests/web/test_prices_service.py
git commit -m "feat(prices): OHLCV 메인 루프 + NaN/inf 행 스킵

_row_is_valid로 OHLC 모든 필드의 finite 검증을 단일 진입점으로 만들었다.
last_close는 마지막 valid 행 기준이라 NaN으로 끝난 시리즈도 안전.
다음 커밋에서 기존 Close-only 픽스처를 OHLCV 픽스처로 갱신한다."
```

---

## Task 4: Backend — 기존 테스트 픽스처를 OHLCV로 갱신

**Files:**
- Modify: `tests/web/test_prices_service.py`(기존 테스트 갱신)

- [ ] **Step 1: 기존 픽스처 갱신**

`tests/web/test_prices_service.py:14-34`의 `test_get_history_returns_points`를 다음으로 교체:

```python
def test_get_history_returns_points(monkeypatch):
    captured = {"calls": 0}

    def fake_download(ticker, start, end, interval, progress=False, auto_adjust=True):
        captured["calls"] += 1
        import pandas as pd
        idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
        return pd.DataFrame(
            {
                "Open":   [179.0, 180.0],
                "High":   [181.0, 182.5],
                "Low":    [178.5, 179.4],
                "Close":  [180.0, 181.5],
                "Volume": [10_000, 12_345],
            },
            index=idx,
        )

    monkeypatch.setattr(svc, "_yf_download", fake_download)

    out = svc.get_price_history("aapl", days=5)
    assert out.ticker == "AAPL"
    assert len(out.points) == 2
    assert out.last_close == 181.5
    assert captured["calls"] == 1

    again = svc.get_price_history("AAPL", days=5)
    assert again.last_close == 181.5
    assert captured["calls"] == 1
```

- [ ] **Step 2: 멀티컬럼 ticker 회귀 테스트 갱신**

`_multi_close_frame` 헬퍼는 OHLCV 5컬럼이 모두 있는 형태로 옮겨야 한다. 기존 함수를 다음으로 교체:

```python
def _multi_ohlcv_full(close_by_ticker: dict[str, list[float]]):
    """OHLCV 전체가 (field, ticker) MultiIndex로 들어온 yfinance 응답 모방."""
    import pandas as pd
    idx = pd.to_datetime(["2026-04-21", "2026-04-22"])
    fields = ["Open", "High", "Low", "Close", "Volume"]
    cols = pd.MultiIndex.from_product([fields, list(close_by_ticker)])
    data = {}
    for ticker, closes in close_by_ticker.items():
        for f in fields:
            offset = {"Open": -1, "High": +2, "Low": -2, "Close": 0, "Volume": 1_000}[f]
            if f == "Volume":
                data[(f, ticker)] = [int(c) + offset for c in closes]
            else:
                data[(f, ticker)] = [c + offset for c in closes]
    return pd.DataFrame(data, index=idx, columns=cols)
```

이어서 `test_get_history_picks_requested_ticker_from_multicolumn_frame`와 `test_get_history_drops_frame_when_requested_ticker_missing`을 다음으로 교체:

```python
def test_get_history_picks_requested_ticker_from_multicolumn_frame(monkeypatch):
    def fake_download(*a, **kw):
        return _multi_ohlcv_full({"NFLX": [87.5, 88.27], "GOOGL": [395.0, 397.1]})

    monkeypatch.setattr(svc, "_yf_download", fake_download)
    out = svc.get_price_history("GOOGL", days=5)
    assert out.last_close == 397.1
    assert [p.close for p in out.points] == [395.0, 397.1]


def test_get_history_drops_frame_when_requested_ticker_missing(monkeypatch):
    def fake_download(*a, **kw):
        return _multi_ohlcv_full({"NFLX": [87.5, 88.27]})

    monkeypatch.setattr(svc, "_yf_download", fake_download)
    out = svc.get_price_history("GOOGL", days=5)
    assert out.points == []
    assert out.last_close is None
```

기존 `_multi_close_frame` 함수와 그 헬퍼는 삭제.

- [ ] **Step 3: 전체 백엔드 테스트 통과 확인**

```bash
pytest tests/web/test_prices_service.py tests/web/test_prices_api.py -v
```

Expected: 모든 테스트 PASS.

- [ ] **Step 4: 커밋**

```bash
git add tests/web/test_prices_service.py
git commit -m "test(prices): 기존 픽스처를 OHLCV 5컬럼으로 갱신

Close-only 픽스처는 이제 _row_is_valid에서 스킵되므로,
유효한 OHLCV가 항상 5개 필드 모두 포함하도록 정리."
```

---

## Task 5: Frontend — 의존성 + Vitest 설정 추가

**Files:**
- Modify: `web/package.json`
- Create: `web/vitest.config.ts`

- [ ] **Step 1: 의존성 추가**

```bash
cd web
pnpm add lightweight-charts@^5 date-fns@^3
pnpm add -D vitest@^2 @vitejs/plugin-react@^4 jsdom@^24 @types/jsdom@^21
```

(설치 가능한 최신 메이저 버전을 사용. Lightweight Charts는 v5 이상 필수 — panes API 정식 지원.)

- [ ] **Step 2: Vitest 설정 파일 생성**

`web/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    include: ["**/__tests__/**/*.test.{ts,tsx}"],
    globals: true,
  },
});
```

- [ ] **Step 3: package.json scripts에 `test:unit` 추가**

`web/package.json`의 `scripts` 블록에 라인 추가(다른 라인 손대지 말 것):

```json
    "test:unit": "vitest run",
    "test:unit:watch": "vitest",
```

- [ ] **Step 4: 빈 dummy 테스트로 설정 검증**

`web/components/portfolio/__tests__/setup.test.ts` 생성:

```ts
import { describe, it, expect } from "vitest";

describe("vitest setup", () => {
  it("loads", () => {
    expect(1 + 1).toBe(2);
  });
});
```

```bash
pnpm --dir web test:unit
```

Expected: 1 passed.

- [ ] **Step 5: dummy 테스트 삭제 + 커밋**

```bash
rm web/components/portfolio/__tests__/setup.test.ts
git -C .. add web/package.json web/pnpm-lock.yaml web/vitest.config.ts
git -C .. commit -m "chore(web): lightweight-charts v5 + vitest 설정 추가

캔들 차트 구현용 의존성. 단위 테스트는 components/**/__tests__/ 하에
*.test.ts(x)로 둔다."
```

(주의: `pnpm-lock.yaml`이 web/ 안에 있는지 루트에 있는지 확인 후 정확한 경로로 add.)

---

## Task 6: Frontend — `lib/prices.ts` 타입 동기화

**Files:**
- Modify: `web/lib/prices.ts`

- [ ] **Step 1: PricePoint 인터페이스 확장**

`web/lib/prices.ts`를 다음으로 교체:

```ts
import { api } from "./api";

export interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PriceHistoryResponse {
  ticker: string;
  points: PricePoint[];
  last_close: number | null;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export async function getPriceHistory(
  ticker: string,
  days: number = 90,
): Promise<PriceHistoryResponse> {
  return api(
    `${BASE}/api/prices/${encodeURIComponent(ticker)}/history?days=${days}`,
  );
}
```

- [ ] **Step 2: 타입체크 실행**

```bash
pnpm --dir web typecheck
```

Expected: 기존 `price-chart.tsx`/`indicator-panel.tsx`가 `PricePoint`를 `{ date, close }`로만 사용했다면 그대로 통과. 타입 에러 발생 시 사용처가 새 필드를 추가로 요구하지 않는지 확인(어차피 다음 Task에서 모두 교체됨).

- [ ] **Step 3: 커밋**

```bash
git add web/lib/prices.ts
git commit -m "feat(web): PricePoint 타입에 OHLCV 필드 추가

백엔드 응답 스키마와 동기화. 기존 사용처는 close만 읽으므로 영향 없음."
```

---

## Task 7: Frontend — `bucketKey` (TDD)

**Files:**
- Create: `web/components/portfolio/candle-chart/resample.ts`
- Test: `web/components/portfolio/__tests__/resample.test.ts`

- [ ] **Step 1: 실패 테스트 작성**

`web/components/portfolio/__tests__/resample.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { bucketKey } from "../candle-chart/resample";

describe("bucketKey", () => {
  it("1D returns the input date unchanged", () => {
    expect(bucketKey("2026-04-22", "1D")).toBe("2026-04-22");
  });

  it("1W returns the ISO Monday for any weekday", () => {
    // 2026-04-22 = Wednesday → Monday is 2026-04-20
    expect(bucketKey("2026-04-22", "1W")).toBe("2026-04-20");
    // 2026-04-20 (Monday) → itself
    expect(bucketKey("2026-04-20", "1W")).toBe("2026-04-20");
    // 2026-04-26 (Sunday, last day of ISO week) → 2026-04-20
    expect(bucketKey("2026-04-26", "1W")).toBe("2026-04-20");
    // 2026-04-27 (next Monday) → 2026-04-27
    expect(bucketKey("2026-04-27", "1W")).toBe("2026-04-27");
  });

  it("1M returns the first day of the month", () => {
    expect(bucketKey("2026-04-22", "1M")).toBe("2026-04-01");
    expect(bucketKey("2026-04-01", "1M")).toBe("2026-04-01");
    expect(bucketKey("2026-12-31", "1M")).toBe("2026-12-01");
  });
});
```

- [ ] **Step 2: 테스트 실행으로 실패 확인**

```bash
pnpm --dir web test:unit -- resample
```

Expected: FAIL — `Cannot find module '../candle-chart/resample'`.

- [ ] **Step 3: 구현**

`web/components/portfolio/candle-chart/resample.ts`:

```ts
import { startOfISOWeek, format, parseISO } from "date-fns";

export type Interval = "1D" | "1W" | "1M";

/**
 * 일봉 날짜 문자열(YYYY-MM-DD)을 인터벌 bucket의 대표 날짜로 변환.
 *
 * - 1D: 항등
 * - 1W: 해당 ISO 주의 월요일
 * - 1M: 해당 월의 1일
 */
export function bucketKey(date: string, interval: Interval): string {
  if (interval === "1D") return date;
  if (interval === "1W") {
    const monday = startOfISOWeek(parseISO(date));
    return format(monday, "yyyy-MM-dd");
  }
  // "1M"
  return date.slice(0, 7) + "-01";
}
```

- [ ] **Step 4: 테스트 실행으로 통과 확인**

```bash
pnpm --dir web test:unit -- resample
```

Expected: 3 passed.

- [ ] **Step 5: 커밋**

```bash
git add web/components/portfolio/candle-chart/resample.ts web/components/portfolio/__tests__/resample.test.ts
git commit -m "feat(chart): bucketKey — 인터벌별 대표 날짜 변환

캔들과 신호 마커가 같은 함수로 시간 키를 정렬해 인터벌 전환에서
마커가 어긋나지 않도록 한다."
```

---

## Task 8: Frontend — `resample` (TDD)

**Files:**
- Modify: `web/components/portfolio/candle-chart/resample.ts`
- Test: `web/components/portfolio/__tests__/resample.test.ts`

- [ ] **Step 1: 실패 테스트 추가**

`web/components/portfolio/__tests__/resample.test.ts`에 추가:

```ts
import { resample } from "../candle-chart/resample";
import type { PricePoint } from "@/lib/prices";

const mk = (d: string, o: number, h: number, l: number, c: number, v: number): PricePoint =>
  ({ date: d, open: o, high: h, low: l, close: c, volume: v });

describe("resample", () => {
  it("1D returns input as-is", () => {
    const daily = [mk("2026-04-22", 1, 2, 0.5, 1.5, 10)];
    expect(resample(daily, "1D")).toEqual(daily);
  });

  it("returns empty for empty input", () => {
    expect(resample([], "1W")).toEqual([]);
    expect(resample([], "1M")).toEqual([]);
  });

  it("aggregates a full ISO week to one weekly bar", () => {
    // 2026-04-20 (Mon) ~ 2026-04-24 (Fri)
    const daily = [
      mk("2026-04-20", 100, 105, 99, 104, 1000),
      mk("2026-04-21", 104, 108, 103, 107, 1100),
      mk("2026-04-22", 107, 110, 106, 108, 1200),
      mk("2026-04-23", 108, 112, 107, 111, 1300),
      mk("2026-04-24", 111, 113, 109, 112, 1400),
    ];
    const out = resample(daily, "1W");
    expect(out).toHaveLength(1);
    expect(out[0]).toEqual({
      date: "2026-04-20",
      open: 100,    // 첫 거래일 open
      high: 113,    // max(high)
      low: 99,      // min(low)
      close: 112,   // 마지막 거래일 close
      volume: 6000, // sum
    });
  });

  it("splits across week boundaries", () => {
    // Friday 2026-04-24 + Monday 2026-04-27 → 2 weekly bars
    const daily = [
      mk("2026-04-24", 100, 105, 99, 104, 1000),
      mk("2026-04-27", 104, 110, 103, 108, 2000),
    ];
    const out = resample(daily, "1W");
    expect(out.map((p) => p.date)).toEqual(["2026-04-20", "2026-04-27"]);
    expect(out[0].volume).toBe(1000);
    expect(out[1].volume).toBe(2000);
  });

  it("aggregates a month to one monthly bar", () => {
    const daily = [
      mk("2026-04-01", 100, 110, 99, 105, 100),
      mk("2026-04-15", 105, 115, 104, 112, 200),
      mk("2026-04-30", 112, 120, 111, 118, 300),
    ];
    const out = resample(daily, "1M");
    expect(out).toEqual([
      { date: "2026-04-01", open: 100, high: 120, low: 99, close: 118, volume: 600 },
    ]);
  });
});
```

- [ ] **Step 2: 테스트 실행으로 실패 확인**

```bash
pnpm --dir web test:unit -- resample
```

Expected: FAIL — `resample is not a function`.

- [ ] **Step 3: 구현 추가**

`web/components/portfolio/candle-chart/resample.ts` 끝에 추가:

```ts
import type { PricePoint } from "@/lib/prices";

/**
 * 일봉 시리즈를 주봉 또는 월봉으로 압축. 시간순 정렬된 입력을 가정한다.
 */
export function resample(daily: PricePoint[], interval: Interval): PricePoint[] {
  if (interval === "1D") return daily;
  if (daily.length === 0) return [];

  type Acc = {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  };
  const buckets = new Map<string, Acc>();
  for (const p of daily) {
    const key = bucketKey(p.date, interval);
    const acc = buckets.get(key);
    if (!acc) {
      buckets.set(key, {
        date: key,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
        volume: p.volume,
      });
    } else {
      acc.high = Math.max(acc.high, p.high);
      acc.low = Math.min(acc.low, p.low);
      acc.close = p.close;
      acc.volume += p.volume;
    }
  }
  return [...buckets.values()];
}
```

- [ ] **Step 4: 테스트 실행으로 통과 확인**

```bash
pnpm --dir web test:unit -- resample
```

Expected: 8 passed.

- [ ] **Step 5: 커밋**

```bash
git add web/components/portfolio/candle-chart/resample.ts web/components/portfolio/__tests__/resample.test.ts
git commit -m "feat(chart): resample — 일봉을 주/월봉으로 압축

같은 bucket의 OHLC는 first-open / max-high / min-low / last-close,
volume은 합산. 1D는 항등."
```

---

## Task 9: Frontend — `alignSignals` (TDD)

**Files:**
- Modify: `web/components/portfolio/candle-chart/resample.ts`
- Test: `web/components/portfolio/__tests__/resample.test.ts`

- [ ] **Step 1: 실패 테스트 추가**

`__tests__/resample.test.ts`에 추가:

```ts
import { alignSignals } from "../candle-chart/resample";
import type { SignalMarker } from "@/components/portfolio/price-chart";

const sig = (date: string, decision: SignalMarker["decision"], close: number): SignalMarker =>
  ({ date, decision, close });

describe("alignSignals", () => {
  it("1D returns input unchanged", () => {
    const s = [sig("2026-04-22", "BUY", 100)];
    expect(alignSignals(s, "1D")).toEqual(s);
  });

  it("1W remaps date to the ISO Monday", () => {
    const out = alignSignals([sig("2026-04-22", "BUY", 100)], "1W");
    expect(out).toEqual([{ date: "2026-04-20", decision: "BUY", close: 100 }]);
  });

  it("collapses multiple signals in one bucket to the first (most recent)", () => {
    // 입력은 created_at DESC 정렬 가정 — 첫 번째가 최신.
    const input = [
      sig("2026-04-24", "SELL", 110),
      sig("2026-04-22", "BUY", 100),
      sig("2026-04-20", "HOLD", 95),
    ];
    const out = alignSignals(input, "1W");
    expect(out).toEqual([{ date: "2026-04-20", decision: "SELL", close: 110 }]);
  });

  it("preserves separate buckets across weeks", () => {
    const input = [
      sig("2026-04-27", "BUY", 120),  // 다음 주
      sig("2026-04-22", "SELL", 110), // 이번 주
    ];
    const out = alignSignals(input, "1W");
    expect(out.map((s) => s.date).sort()).toEqual(["2026-04-20", "2026-04-27"]);
  });
});
```

- [ ] **Step 2: 테스트 실행으로 실패 확인**

```bash
pnpm --dir web test:unit -- resample
```

Expected: FAIL — `alignSignals is not a function`.

- [ ] **Step 3: 구현 추가**

`web/components/portfolio/candle-chart/resample.ts` 끝에 추가:

```ts
import type { SignalMarker } from "@/components/portfolio/price-chart";

/**
 * 신호 마커의 date를 인터벌 bucket key로 리맵.
 *
 * 한 bucket에 신호가 여러 개면 입력 순서상 첫 번째(가장 최신)만 유지한다.
 * 이는 page.tsx에서 created_at DESC 정렬 + seenDates 정책과 일관된다.
 */
export function alignSignals(
  signals: SignalMarker[],
  interval: Interval,
): SignalMarker[] {
  if (interval === "1D") return signals;
  const seen = new Map<string, SignalMarker>();
  for (const s of signals) {
    const key = bucketKey(s.date, interval);
    if (seen.has(key)) continue;
    seen.set(key, { ...s, date: key });
  }
  return [...seen.values()];
}
```

- [ ] **Step 4: 테스트 실행으로 통과 확인**

```bash
pnpm --dir web test:unit -- resample
```

Expected: 12 passed (cumulative).

- [ ] **Step 5: 커밋**

```bash
git add web/components/portfolio/candle-chart/resample.ts web/components/portfolio/__tests__/resample.test.ts
git commit -m "feat(chart): alignSignals — 인터벌 bucket으로 신호 마커 리맵

bucketKey를 캔들과 마커가 공유하지 않으면 주/월 탭에서 마커가 사라지거나
잘못된 캔들 위에 놓인다. 한 bucket의 최신 1개만 유지하는 정책은
page.tsx의 seenDates 로직과 일관."
```

---

## Task 10: Frontend — `series-config.ts` + `CandleChart` 골격

**Files:**
- Create: `web/components/portfolio/candle-chart/series-config.ts`
- Create: `web/components/portfolio/candle-chart/candle-chart.tsx`
- Create: `web/components/portfolio/candle-chart/index.ts`

- [ ] **Step 1: 색상 상수 파일**

`web/components/portfolio/candle-chart/series-config.ts`:

```ts
export const CHART = {
  up: "#F04452",          // KR convention: 상승 = 빨강 (signal.buy)
  down: "#1B64DA",        // 하락 = 파랑 (signal.sell)
  hold: "#8B95A1",        // text-3
  axis: "#C0C8CF",        // border-2
  grid: "#EAECEF",        // border-1
  text: "#4E5968",        // text-2
  background: "#FFFFFF",  // bg-1
  ma5: "#F59E0B",
  ma20: "#06B6D4",
  ma60: "#7C3AED",
  ma120: "#8B95A1",
  volumeUp: "rgba(240, 68, 82, 0.45)",
  volumeDown: "rgba(27, 100, 218, 0.45)",
  volumeMa: "#3182F6",
  avgCost: "#8B95A1",
  ema: "#06B6D4",
  bbBand: "#C0C8CF",
  bbMid: "#8B95A1",
  rsi: "#7C3AED",
  stochK: "#F04452",
  stochD: "#1B64DA",
  threshold: "#D1D6DB",
} as const;
```

- [ ] **Step 2: 메인 컴포넌트 골격 (캔들만)**

`web/components/portfolio/candle-chart/candle-chart.tsx`:

```tsx
"use client";
import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { PricePoint } from "@/lib/prices";
import type { SignalMarker } from "@/components/portfolio/price-chart";
import type { ChartSettings } from "@/lib/chart-settings";
import { CHART } from "./series-config";

export interface CandleChartProps {
  points: PricePoint[];
  signals?: SignalMarker[];
  avgCost?: number;
  settings: ChartSettings;
  onSettingsChange: (next: ChartSettings) => void;
  onSettingsReset: () => void;
  height?: number;
}

export function CandleChart({ points, height = 480 }: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: CHART.background },
        textColor: CHART.text,
      },
      grid: {
        vertLines: { color: CHART.grid },
        horzLines: { color: CHART.grid },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: CHART.axis },
      timeScale: { borderColor: CHART.axis, timeVisible: false },
      autoSize: true,
    });
    const candle = chart.addCandlestickSeries({
      upColor: CHART.up,
      downColor: CHART.down,
      borderUpColor: CHART.up,
      borderDownColor: CHART.down,
      wickUpColor: CHART.up,
      wickDownColor: CHART.down,
    });
    chartRef.current = chart;
    candleRef.current = candle;
    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!candleRef.current) return;
    candleRef.current.setData(
      points.map((p) => ({
        time: p.date as Time,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      })),
    );
    chartRef.current?.timeScale().fitContent();
  }, [points]);

  return <div ref={containerRef} style={{ height, width: "100%" }} />;
}
```

(주의: Lightweight Charts v5 API. `addCandlestickSeries` 메서드명/시그니처는 v5 docs와 정확히 일치하는지 한 번 더 확인 — 변경 시 컴파일러가 잡아준다.)

- [ ] **Step 3: 외부 export**

`web/components/portfolio/candle-chart/index.ts`:

```ts
export { CandleChart } from "./candle-chart";
export type { CandleChartProps } from "./candle-chart";
export { bucketKey, resample, alignSignals } from "./resample";
export type { Interval } from "./resample";
```

- [ ] **Step 4: 타입체크 + dev 서버 수동 확인**

```bash
pnpm --dir web typecheck
```

이어서 별도 임시 페이지 또는 `[ticker]/page.tsx`에 임시로 `<CandleChart points={price?.points ?? []} ... />`를 끼워 넣어 dev 서버에서 캔들이 그려지는지 눈으로 확인:

```bash
pnpm --dir web dev
```

브라우저에서 `/portfolio/AAPL`(또는 보유 종목) 접속 → 빨강/파랑 캔들이 보이고 마우스 휠로 줌이 되는지 확인. 임시로 끼워 넣은 코드는 다음 Task 들에서 어차피 정식 통합되므로 그대로 둔다.

- [ ] **Step 5: 커밋**

```bash
git add web/components/portfolio/candle-chart/
git commit -m "feat(chart): CandleChart 골격 — Lightweight Charts 캔들 시리즈

색상 상수와 차트 인스턴스 라이프사이클만. 거래량/MA/마커는 후속 커밋."
```

---

## Task 11: Frontend — 거래량 pane + 20MA + 인터벌 탭

**Files:**
- Modify: `web/components/portfolio/candle-chart/candle-chart.tsx`
- Create: `web/components/portfolio/candle-chart/interval-tabs.tsx`

- [ ] **Step 1: `IntervalTabs` 컴포넌트**

`web/components/portfolio/candle-chart/interval-tabs.tsx`:

```tsx
"use client";
import { cn } from "@/lib/utils";
import type { Interval } from "./resample";

const TABS: { key: Interval; label: string }[] = [
  { key: "1D", label: "일" },
  { key: "1W", label: "주" },
  { key: "1M", label: "월" },
];

export function IntervalTabs({
  value,
  onChange,
}: {
  value: Interval;
  onChange: (next: Interval) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-border-1 bg-bg-2/50 p-0.5 text-xs font-mono">
      {TABS.map((t) => (
        <button
          key={t.key}
          type="button"
          onClick={() => onChange(t.key)}
          className={cn(
            "px-3 py-1 rounded-sm transition-colors",
            value === t.key
              ? "bg-bg-1 text-text-1 shadow-sm"
              : "text-text-3 hover:text-text-2",
          )}
          aria-pressed={value === t.key}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: `CandleChart`에 인터벌·거래량·SMA 통합**

`web/components/portfolio/candle-chart/candle-chart.tsx`를 다음으로 교체:

```tsx
"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import type { PricePoint } from "@/lib/prices";
import type { SignalMarker } from "@/components/portfolio/price-chart";
import type { ChartSettings } from "@/lib/chart-settings";
import { sma } from "@/lib/indicators";
import { CHART } from "./series-config";
import { IntervalTabs } from "./interval-tabs";
import { resample, type Interval } from "./resample";

export interface CandleChartProps {
  points: PricePoint[];
  signals?: SignalMarker[];
  avgCost?: number;
  settings: ChartSettings;
  onSettingsChange: (next: ChartSettings) => void;
  onSettingsReset: () => void;
  height?: number;
}

export function CandleChart({ points, height = 480 }: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const volumeMaRef = useRef<ISeriesApi<"Line"> | null>(null);
  const sma5Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const sma20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const sma60Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const sma120Ref = useRef<ISeriesApi<"Line"> | null>(null);

  const [interval, setInterval] = useState<Interval>("1D");

  // interval 변경 후 시간축 보존을 위해 직전 visible range를 잡아둔다.
  const savedRangeRef = useRef<{ from: Time; to: Time } | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: CHART.background },
        textColor: CHART.text,
      },
      grid: {
        vertLines: { color: CHART.grid },
        horzLines: { color: CHART.grid },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: CHART.axis },
      timeScale: { borderColor: CHART.axis, timeVisible: false },
      autoSize: true,
    });
    const candle = chart.addCandlestickSeries({
      upColor: CHART.up,
      downColor: CHART.down,
      borderUpColor: CHART.up,
      borderDownColor: CHART.down,
      wickUpColor: CHART.up,
      wickDownColor: CHART.down,
    });
    // 거래량은 별도 priceScale로 메인 차트의 하단 25%에 띄운다.
    candle.priceScale().applyOptions({ scaleMargins: { top: 0.05, bottom: 0.3 } });
    const volume = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      color: CHART.volumeUp,
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.75, bottom: 0 },
    });
    const volumeMa = chart.addLineSeries({
      priceScaleId: "vol",
      color: CHART.volumeMa,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const sma5 = chart.addLineSeries({
      color: CHART.ma5,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const sma20 = chart.addLineSeries({
      color: CHART.ma20,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const sma60 = chart.addLineSeries({
      color: CHART.ma60,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const sma120 = chart.addLineSeries({
      color: CHART.ma120,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chartRef.current = chart;
    candleRef.current = candle;
    volumeRef.current = volume;
    volumeMaRef.current = volumeMa;
    sma5Ref.current = sma5;
    sma20Ref.current = sma20;
    sma60Ref.current = sma60;
    sma120Ref.current = sma120;
    return () => {
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
      volumeMaRef.current = null;
      sma5Ref.current = null;
      sma20Ref.current = null;
      sma60Ref.current = null;
      sma120Ref.current = null;
    };
  }, []);

  const series = useMemo(() => resample(points, interval), [points, interval]);

  useEffect(() => {
    if (!candleRef.current || !volumeRef.current) return;
    if (!sma5Ref.current || !sma20Ref.current) return;
    if (!sma60Ref.current || !sma120Ref.current) return;
    if (!volumeMaRef.current) return;

    candleRef.current.setData(
      series.map((p) => ({
        time: p.date as Time,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      })),
    );
    volumeRef.current.setData(
      series.map((p) => ({
        time: p.date as Time,
        value: p.volume,
        color: p.close >= p.open ? CHART.volumeUp : CHART.volumeDown,
      })),
    );
    const closes = series.map((p) => p.close);
    const volumes = series.map((p) => p.volume);
    const setLine = (
      ref: ISeriesApi<"Line">,
      values: (number | null)[],
      times: string[],
    ) => {
      ref.setData(
        values
          .map((v, i) => (v == null ? null : { time: times[i] as Time, value: v }))
          .filter((d): d is { time: Time; value: number } => d != null),
      );
    };
    const times = series.map((p) => p.date);
    setLine(sma5Ref.current, sma(closes, 5), times);
    setLine(sma20Ref.current, sma(closes, 20), times);
    setLine(sma60Ref.current, sma(closes, 60), times);
    setLine(sma120Ref.current, sma(closes, 120), times);
    setLine(volumeMaRef.current, sma(volumes, 20), times);

    // 줌 보존: 직전 인터벌의 visible range가 있으면 복원, 없으면 fitContent.
    if (savedRangeRef.current) {
      try {
        chartRef.current?.timeScale().setVisibleRange(savedRangeRef.current);
      } catch {
        chartRef.current?.timeScale().fitContent();
      }
    } else {
      chartRef.current?.timeScale().fitContent();
    }
  }, [series]);

  const handleIntervalChange = (next: Interval) => {
    // 현재 visible range 저장.
    const range = chartRef.current?.timeScale().getVisibleRange();
    if (range) savedRangeRef.current = range;
    setInterval(next);
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <IntervalTabs value={interval} onChange={handleIntervalChange} />
      </div>
      <div ref={containerRef} style={{ height, width: "100%" }} />
    </div>
  );
}
```

- [ ] **Step 3: 타입체크**

```bash
pnpm --dir web typecheck
```

Expected: PASS.

- [ ] **Step 4: dev 서버에서 시각 확인**

```bash
pnpm --dir web dev
```

`/portfolio/<ticker>`에서:
- 캔들이 KR 컨벤션(상승 빨강/하락 파랑)으로 보이는지
- 하단 25%에 거래량 히스토그램과 파란 20MA 라인이 보이는지
- 4개 SMA 선(노/시안/보라/회색)이 보이는지
- 일/주/월 탭 클릭 시 캔들 수가 줄어들고 보던 시점이 그대로 유지되는지

- [ ] **Step 5: 커밋**

```bash
git add web/components/portfolio/candle-chart/
git commit -m "feat(chart): 거래량 pane + 20MA + SMA 4종 + 인터벌 탭

거래량은 별도 priceScale로 하단 25%, SMA는 메인에 4선 고정.
인터벌 전환 시 visible range를 시간 기반으로 복원해 시점 유지."
```

---

## Task 12: Frontend — OHLC 헤더 + 크로스헤어 동기화

**Files:**
- Create: `web/components/portfolio/candle-chart/ohlc-header.tsx`
- Modify: `web/components/portfolio/candle-chart/candle-chart.tsx`

- [ ] **Step 1: OHLC 헤더 컴포넌트**

`web/components/portfolio/candle-chart/ohlc-header.tsx`:

```tsx
"use client";
import { formatPrice, useCurrency, type CurrencyCtx } from "@/lib/currency";
import { cn } from "@/lib/utils";
import type { PricePoint } from "@/lib/prices";

interface OhlcHeaderProps {
  current: PricePoint | null;
  prevClose: number | null; // 전 봉 종가, 변동률 기준
}

function pctText(value: number, base: number): string {
  if (!base) return "0.00%";
  return ((value - base) / base * 100).toFixed(2) + "%";
}

function pctClass(value: number, base: number): string {
  if (!base || value === base) return "text-text-3";
  return value > base ? "text-signal-buy" : "text-signal-sell";
}

function Field({
  label,
  value,
  base,
  ctx,
}: {
  label: string;
  value: number;
  base: number | null;
  ctx: Pick<CurrencyCtx, "currency" | "fxRate">;
}) {
  const hasBase = base != null;
  return (
    <div className="flex items-baseline gap-1.5 font-mono text-2xs">
      <span className="text-text-3">{label}</span>
      <span className="tabular-nums text-text-1">
        {formatPrice(value, ctx)}
      </span>
      {hasBase && (
        <span className={cn("tabular-nums", pctClass(value, base!))}>
          ({value >= base! ? "+" : ""}
          {pctText(value, base!)})
        </span>
      )}
    </div>
  );
}

export function OhlcHeader({ current, prevClose }: OhlcHeaderProps) {
  const ctx = useCurrency();
  if (!current) return <div className="h-6" />;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      <Field label="시가" value={current.open} base={prevClose} ctx={ctx} />
      <Field label="고가" value={current.high} base={prevClose} ctx={ctx} />
      <Field label="저가" value={current.low} base={prevClose} ctx={ctx} />
      <Field label="종가" value={current.close} base={prevClose} ctx={ctx} />
    </div>
  );
}
```

- [ ] **Step 2: `CandleChart`에서 크로스헤어 구독 + 헤더 렌더**

`candle-chart.tsx` 컴포넌트 본문에 hovered 상태 + 구독 추가. 다음 코드 조각을 표시된 위치에 끼워 넣는다(전체 파일이 아니라 추가/변경되는 부분만 보여줌).

`useState` 옆에:

```tsx
const [hovered, setHovered] = useState<PricePoint | null>(null);
```

차트 init `useEffect` 내, `chartRef.current = chart;` 직전 줄에:

```tsx
chart.subscribeCrosshairMove((param) => {
  if (!param.time || !param.seriesData.size) {
    setHovered(null);
    return;
  }
  // candle series 데이터에서 해당 시점 OHLC 찾기.
  const c = param.seriesData.get(candle) as
    | { time: Time; open: number; high: number; low: number; close: number }
    | undefined;
  if (!c) {
    setHovered(null);
    return;
  }
  setHovered({
    date: String(param.time),
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
    volume: 0, // 헤더는 OHLC만 사용
  });
});
```

return 부분을 다음으로 교체:

```tsx
const headerCurrent = hovered ?? series[series.length - 1] ?? null;
const headerPrev = (() => {
  if (!headerCurrent) return null;
  const idx = series.findIndex((p) => p.date === headerCurrent.date);
  if (idx <= 0) return null;
  return series[idx - 1].close;
})();

return (
  <div className="flex flex-col gap-2">
    <div className="flex items-center justify-between gap-3">
      <OhlcHeader current={headerCurrent} prevClose={headerPrev} />
      <IntervalTabs value={interval} onChange={handleIntervalChange} />
    </div>
    <div ref={containerRef} style={{ height, width: "100%" }} />
  </div>
);
```

(상단의 import에 `OhlcHeader` 추가:)

```tsx
import { OhlcHeader } from "./ohlc-header";
```

- [ ] **Step 3: 타입체크**

```bash
pnpm --dir web typecheck
```

- [ ] **Step 4: dev 서버 확인**

마우스를 차트에 올리면 헤더 OHLC가 호버 봉 기준으로 갱신되고, 호버를 떼면 마지막 봉으로 돌아오는지. 변동률 색이 KR 컨벤션(빨/파)인지.

- [ ] **Step 5: 커밋**

```bash
git add web/components/portfolio/candle-chart/
git commit -m "feat(chart): OHLC 헤더 + 크로스헤어 동기화

호버 봉의 시·고·저·종을 상단에 표시. 변동률은 직전 봉 종가 대비,
색은 KR 컨벤션(상승=signal-buy, 하락=signal-sell)."
```

---

## Task 13: Frontend — 신호 마커 + 평단가 라인

**Files:**
- Modify: `web/components/portfolio/candle-chart/candle-chart.tsx`

- [ ] **Step 1: 마커·평단가 적용 로직 추가**

`candle-chart.tsx`의 import에 추가:

```tsx
import { alignSignals } from "./resample";
import type { IPriceLine } from "lightweight-charts";
```

기존 props 구조분해를 다음으로 확장:

```tsx
export function CandleChart({
  points,
  signals = [],
  avgCost,
  height = 480,
}: CandleChartProps) {
```

`useRef` 블록 끝에 추가:

```tsx
const avgCostLineRef = useRef<IPriceLine | null>(null);
```

마커 매핑 헬퍼를 컴포넌트 함수 위에 추가:

```tsx
const MARKER_STYLE: Record<
  SignalMarker["decision"],
  { position: "aboveBar" | "belowBar" | "inBar"; shape: "arrowUp" | "arrowDown" | "circle"; color: string; text: string }
> = {
  BUY:          { position: "belowBar", shape: "arrowUp",   color: CHART.up,   text: "BUY" },
  OVERWEIGHT:   { position: "belowBar", shape: "arrowUp",   color: CHART.up,   text: "OW"  },
  SELL:         { position: "aboveBar", shape: "arrowDown", color: CHART.down, text: "SELL"},
  UNDERWEIGHT:  { position: "aboveBar", shape: "arrowDown", color: CHART.down, text: "UW"  },
  HOLD:         { position: "inBar",    shape: "circle",    color: CHART.hold, text: "HOLD"},
};
```

데이터 적용 `useEffect`(series 의존성) 안에서, 마지막 `fitContent` 처리 직전에 추가:

```tsx
// 신호 마커
const aligned = alignSignals(signals, interval);
candleRef.current.setMarkers(
  aligned.map((s) => ({
    time: s.date as Time,
    position: MARKER_STYLE[s.decision].position,
    shape: MARKER_STYLE[s.decision].shape,
    color: MARKER_STYLE[s.decision].color,
    text: MARKER_STYLE[s.decision].text,
  })),
);
```

평단가 라인 — 별도 `useEffect`로 분리:

```tsx
useEffect(() => {
  if (!candleRef.current) return;
  if (avgCostLineRef.current) {
    candleRef.current.removePriceLine(avgCostLineRef.current);
    avgCostLineRef.current = null;
  }
  if (avgCost == null || !Number.isFinite(avgCost)) return;
  avgCostLineRef.current = candleRef.current.createPriceLine({
    price: avgCost,
    color: CHART.avgCost,
    lineStyle: 2, // dashed
    lineWidth: 1,
    axisLabelVisible: true,
    title: "Avg",
  });
}, [avgCost]);
```

(useEffect 의존성에 `signals`, `interval` 포함되도록 주의 — 기존 series effect에 signals/interval이 의존성으로 들어가야 마커가 갱신된다. series effect 의존성 배열을 `[series, signals, interval]`로 확장.)

- [ ] **Step 2: 타입체크**

```bash
pnpm --dir web typecheck
```

- [ ] **Step 3: dev 서버 확인**

분석이 있는 종목(예: AAPL — 분석 1개 이상 있는 ticker)을 열어:
- BUY는 봉 아래 빨간 위 화살표, SELL은 봉 위 파란 아래 화살표가 보이는지
- 평단가 라인이 점선 + 우측 "Avg" 라벨로 보이는지
- 일→주 탭 전환 시 마커가 사라지지 않고 같은 자리(주 단위)에 남아 있는지

- [ ] **Step 4: 커밋**

```bash
git add web/components/portfolio/candle-chart/candle-chart.tsx
git commit -m "feat(chart): BUY/SELL/HOLD 마커 + 평단가 가격 라인

마커는 alignSignals로 인터벌 bucket에 정렬, 평단가는 createPriceLine
으로 우측 라벨 포함 점선 표시."
```

---

## Task 14: Frontend — `series-builder.ts` (EMA/Bollinger/RSI/Stoch)

**Files:**
- Create: `web/components/portfolio/candle-chart/series-builder.ts`
- Modify: `web/components/portfolio/candle-chart/candle-chart.tsx`

- [ ] **Step 1: 어댑터 모듈 생성**

`web/components/portfolio/candle-chart/series-builder.ts`:

```ts
import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import type { ChartSettings } from "@/lib/chart-settings";
import type { PricePoint } from "@/lib/prices";
import { ema, bollinger, rsi, stochasticSlow } from "@/lib/indicators";
import { CHART } from "./series-config";

/**
 * settings 토글에 따라 차트에 추가/제거되는 옵션 시리즈들을 관리.
 * 캔들·SMA·거래량은 항상 켜져 있으므로 candle-chart.tsx 본체에서 다룬다.
 */
export interface OptionalSeries {
  ema: ISeriesApi<"Line"> | null;
  bbUp: ISeriesApi<"Line"> | null;
  bbMid: ISeriesApi<"Line"> | null;
  bbLo: ISeriesApi<"Line"> | null;
  rsi: ISeriesApi<"Line"> | null;
  stochK: ISeriesApi<"Line"> | null;
  stochD: ISeriesApi<"Line"> | null;
}

export const EMPTY_OPTIONAL: OptionalSeries = {
  ema: null,
  bbUp: null,
  bbMid: null,
  bbLo: null,
  rsi: null,
  stochK: null,
  stochD: null,
};

const RSI_PANE = 2;
const STOCH_PANE = 3;

function setLine(
  ref: ISeriesApi<"Line">,
  values: (number | null)[],
  times: string[],
) {
  ref.setData(
    values
      .map((v, i) => (v == null ? null : { time: times[i] as Time, value: v }))
      .filter((d): d is { time: Time; value: number } => d != null),
  );
}

/**
 * settings의 토글 on/off 변화에 맞춰 시리즈를 추가/제거하고 데이터를 채운다.
 * 시리즈 핸들의 동일성을 유지해 캔들·SMA가 깜빡이지 않는다.
 */
export function syncOptionalSeries(
  chart: IChartApi,
  series: PricePoint[],
  settings: ChartSettings,
  refs: OptionalSeries,
): OptionalSeries {
  const next: OptionalSeries = { ...refs };
  const closes = series.map((p) => p.close);
  const times = series.map((p) => p.date);

  // EMA
  if (settings.overlays.ema.on) {
    if (!next.ema) {
      next.ema = chart.addLineSeries({
        color: CHART.ema,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    setLine(next.ema, ema(closes, settings.overlays.ema.period), times);
  } else if (next.ema) {
    chart.removeSeries(next.ema);
    next.ema = null;
  }

  // Bollinger
  if (settings.overlays.bollinger.on) {
    const bb = bollinger(
      closes,
      settings.overlays.bollinger.period,
      settings.overlays.bollinger.stddev,
    );
    if (!next.bbMid) {
      next.bbMid = chart.addLineSeries({
        color: CHART.bbMid,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    if (!next.bbUp) {
      next.bbUp = chart.addLineSeries({
        color: CHART.bbBand,
        lineWidth: 1,
        lineStyle: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    if (!next.bbLo) {
      next.bbLo = chart.addLineSeries({
        color: CHART.bbBand,
        lineWidth: 1,
        lineStyle: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });
    }
    setLine(next.bbMid, bb.middle, times);
    setLine(next.bbUp, bb.upper, times);
    setLine(next.bbLo, bb.lower, times);
  } else {
    for (const k of ["bbMid", "bbUp", "bbLo"] as const) {
      const ref = next[k];
      if (ref) {
        chart.removeSeries(ref);
        next[k] = null;
      }
    }
  }

  // RSI (별도 pane)
  if (settings.panels.rsi.on) {
    if (!next.rsi) {
      next.rsi = chart.addLineSeries({
        color: CHART.rsi,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        pane: RSI_PANE,
      });
    }
    setLine(next.rsi, rsi(closes, settings.panels.rsi.period), times);
  } else if (next.rsi) {
    chart.removeSeries(next.rsi);
    next.rsi = null;
  }

  // Stoch (별도 pane)
  if (settings.panels.stoch.on) {
    const { k, d } = stochasticSlow(
      closes,
      settings.panels.stoch.k,
      settings.panels.stoch.slowing,
      settings.panels.stoch.d,
    );
    if (!next.stochK) {
      next.stochK = chart.addLineSeries({
        color: CHART.stochK,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        pane: STOCH_PANE,
      });
    }
    if (!next.stochD) {
      next.stochD = chart.addLineSeries({
        color: CHART.stochD,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        pane: STOCH_PANE,
      });
    }
    setLine(next.stochK, k, times);
    setLine(next.stochD, d, times);
  } else {
    for (const key of ["stochK", "stochD"] as const) {
      const ref = next[key];
      if (ref) {
        chart.removeSeries(ref);
        next[key] = null;
      }
    }
  }

  return next;
}
```

(주의: `pane` 옵션은 Lightweight Charts v5 정식 — v4면 컴파일러가 잡는다. `lib/indicators.ts`의 `stochasticSlow`는 기존 export 그대로 사용. 만약 export 이름이 다르면 indicators.ts에서 확인 후 일치시킨다.)

- [ ] **Step 2: `CandleChart`에서 호출**

`candle-chart.tsx`의 import에 추가:

```tsx
import {
  syncOptionalSeries,
  type OptionalSeries,
  EMPTY_OPTIONAL,
} from "./series-builder";
```

`useRef` 블록에 추가:

```tsx
const optionalRef = useRef<OptionalSeries>({ ...EMPTY_OPTIONAL });
```

별도 `useEffect`로 settings 동기화 추가(series effect 다음에):

```tsx
useEffect(() => {
  if (!chartRef.current) return;
  optionalRef.current = syncOptionalSeries(
    chartRef.current,
    series,
    settings,
    optionalRef.current,
  );
}, [series, settings]);
```

(props에서 `settings` 사용 시작했으므로 함수 시그니처에서 `settings`를 구조분해해야 함:)

```tsx
export function CandleChart({
  points,
  signals = [],
  avgCost,
  settings,
  height = 480,
}: CandleChartProps) {
```

- [ ] **Step 3: 타입체크 + dev 확인**

```bash
pnpm --dir web typecheck
```

dev 서버에서:
- 임시로 `useChartSettings`를 호출해 `settings.overlays.ema.on = true`로 켰을 때 시안색 EMA 라인이 메인 차트에 추가되는지
- `panels.rsi.on = true`일 때 차트 아래에 RSI pane이 새로 생기는지
- 다시 끄면 라인/pane이 제거되는지

(IndicatorToolbar는 다음 Task에서 연결.)

- [ ] **Step 4: 커밋**

```bash
git add web/components/portfolio/candle-chart/series-builder.ts web/components/portfolio/candle-chart/candle-chart.tsx
git commit -m "feat(chart): EMA/Bollinger/RSI/Stoch series-builder 어댑터

ChartSettings 토글 변화에 맞춰 시리즈를 add/remove. 캔들·SMA·거래량은
재생성되지 않아 깜빡이지 않는다. RSI/Stoch는 v5 panes API로 별도 pane."
```

---

## Task 15: Frontend — IndicatorToolbar 연결 + 페이지 통합

**Files:**
- Modify: `web/components/portfolio/candle-chart/candle-chart.tsx`
- Modify: `web/app/(workspace)/portfolio/[ticker]/page.tsx`
- Delete: `web/components/portfolio/price-chart.tsx`, `chart-stack.tsx`, `indicator-panel.tsx`

- [ ] **Step 1: SignalMarker 타입을 신규 위치로 이동**

기존 `SignalMarker`는 `web/components/portfolio/price-chart.tsx`에서 export되고 있다. 이 파일은 삭제할 예정이므로 타입을 옮긴다.

`web/components/portfolio/candle-chart/types.ts` 신규 파일 생성:

```ts
export interface SignalMarker {
  date: string;
  decision: "BUY" | "SELL" | "HOLD" | "OVERWEIGHT" | "UNDERWEIGHT";
  close: number;
}
```

`web/components/portfolio/candle-chart/index.ts`에 추가:

```ts
export type { SignalMarker } from "./types";
```

`candle-chart.tsx`/`series-builder.ts`/`resample.ts`/`__tests__/resample.test.ts`/`series-builder.ts`에서 `import type { SignalMarker } from "@/components/portfolio/price-chart"`를 모두 `import type { SignalMarker } from "./types"`(상대 경로) 또는 `from "@/components/portfolio/candle-chart"`로 교체.

- [ ] **Step 2: `CandleChart`에 IndicatorToolbar 통합**

`candle-chart.tsx` import에 추가:

```tsx
import { IndicatorToolbar } from "@/components/portfolio/indicator-toolbar";
```

return 블록의 상단 헤더 부분을 다음으로 교체:

```tsx
return (
  <div className="flex flex-col gap-2">
    <div className="flex items-center justify-between gap-3 flex-wrap">
      <OhlcHeader current={headerCurrent} prevClose={headerPrev} />
      <div className="flex items-center gap-2">
        <IntervalTabs value={interval} onChange={handleIntervalChange} />
        <IndicatorToolbar
          settings={settings}
          onChange={onSettingsChange}
          onReset={onSettingsReset}
        />
      </div>
    </div>
    <div ref={containerRef} style={{ height, width: "100%" }} />
  </div>
);
```

(props 구조분해에 `onSettingsChange`, `onSettingsReset` 추가.)

- [ ] **Step 3: 페이지 통합**

`web/app/(workspace)/portfolio/[ticker]/page.tsx`의 import 블록에서:

```tsx
import { ChartStack } from "@/components/portfolio/chart-stack";
import { SignalMarker } from "@/components/portfolio/price-chart";
```

를 다음으로 교체:

```tsx
import { CandleChart, type SignalMarker } from "@/components/portfolio/candle-chart";
```

`usePriceHistory(ticker, 90)`을 `usePriceHistory(ticker, 365)`로 교체.

`<ChartStack>` 블록(line ~115-122)을 다음으로 교체:

```tsx
<CandleChart
  points={price?.points ?? []}
  signals={signals}
  avgCost={holding?.avg_cost}
  settings={settings}
  onSettingsChange={setSettings}
  onSettingsReset={reset}
/>
```

카드 헤더 `<CardTitle>Price (90d)</CardTitle>`를 `<CardTitle>Price</CardTitle>`로 변경.

- [ ] **Step 4: 옛 컴포넌트 삭제**

```bash
git rm web/components/portfolio/price-chart.tsx
git rm web/components/portfolio/chart-stack.tsx
git rm web/components/portfolio/indicator-panel.tsx
```

`indicator-toolbar.tsx`와 `indicator-colors.ts`는 보존. 다른 곳에서 사용되지 않는지 확인:

```bash
grep -rn "from \"@/components/portfolio/price-chart\"\|from \"@/components/portfolio/chart-stack\"\|from \"@/components/portfolio/indicator-panel\"" web/ --include="*.tsx" --include="*.ts"
```

Expected: 매치 없음(있다면 위 import 갱신 누락).

- [ ] **Step 5: 빌드 + dev 시각 확인**

```bash
pnpm --dir web typecheck
pnpm --dir web build
```

dev 서버에서 보유 종목 페이지를 열어:
- 차트가 단일 컴포넌트로 렌더되는지
- 우상단에 인터벌 탭 + 보조지표 토글 버튼이 나란히 있는지
- IndicatorToolbar의 EMA/Bollinger/RSI/Stoch 토글이 새 차트에 반영되는지
- localStorage에 저장된 기존 설정이 새 차트에 그대로 적용되는지(다른 ticker로 이동 후 돌아왔을 때 토글 상태 유지)

- [ ] **Step 6: 커밋**

```bash
git add web/
git commit -m "feat(portfolio): 캔들 차트로 페이지 통합 + 옛 Recharts 제거

ChartStack/PriceChart/IndicatorPanel 삭제. IndicatorToolbar는 그대로
재사용해 EMA/Bollinger/RSI/Stoch 토글 UX는 동일."
```

---

## Task 16: E2E + 마커 보존 회귀

**Files:**
- Create: `web/tests/e2e/portfolio.spec.ts`

- [ ] **Step 1: E2E 테스트 작성**

`web/tests/e2e/portfolio.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

// chat.spec.ts와 동일하게 global-setup이 인증 세션을 만든다고 가정.
// 보유 종목 1개 이상이 시드되어 있어야 한다.

test.describe("portfolio detail chart", () => {
  test("renders candle chart and switches intervals", async ({ page }) => {
    await page.goto("/portfolio");
    // 첫 번째 보유 종목으로 이동.
    const firstHoldingLink = page.getByRole("link").filter({ hasText: /[A-Z]{1,5}/ }).first();
    await firstHoldingLink.click();
    // 차트가 렌더된 컨테이너를 확인.
    await expect(page.getByRole("button", { name: "일" })).toBeVisible();

    // 일/주/월 탭이 모두 클릭 가능.
    for (const label of ["주", "월", "일"]) {
      await page.getByRole("button", { name: label }).click();
      await expect(
        page.getByRole("button", { name: label }),
      ).toHaveAttribute("aria-pressed", "true");
    }
  });

  test("indicator toolbar toggles persist across reload", async ({ page }) => {
    await page.goto("/portfolio");
    const firstHoldingLink = page.getByRole("link").filter({ hasText: /[A-Z]{1,5}/ }).first();
    await firstHoldingLink.click();

    // 보조지표 토글: RSI 켜기.
    await page.getByRole("button", { name: /RSI/ }).click();
    await expect(page.getByRole("button", { name: /RSI/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    await page.reload();
    await expect(page.getByRole("button", { name: /RSI/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    // 정리: 다시 끄기.
    await page.getByRole("button", { name: /RSI/ }).click();
  });
});
```

- [ ] **Step 2: E2E 실행**

```bash
pnpm --dir web e2e:setup
pnpm --dir web e2e -- portfolio.spec
```

Expected: 2개 테스트 PASS. 환경 셋업이 안 되어 있다면 메시지에 따라 시드 명령 실행.

- [ ] **Step 3: 단위 테스트도 한 번 더 전체 실행**

```bash
pnpm --dir web test:unit
pytest tests/web/ -v
```

Expected: 모두 PASS.

- [ ] **Step 4: 커밋**

```bash
git add web/tests/e2e/portfolio.spec.ts
git commit -m "test(e2e): 포트폴리오 캔들 차트 — 인터벌 + 보조지표 회귀

차트 렌더, 일/주/월 전환, RSI 토글의 localStorage 영속성을 확인."
```

---

## 마무리

- [ ] **모든 변경 PR 준비**

```bash
git log --oneline main..HEAD
```

Expected: 16개 안팎의 커밋. 본인이 직접 push/PR을 만들 시점에 사용자에게 확인.

- [ ] **dev 서버에서 한 번 더 종합 확인**

브라우저에서:
1. 캔들이 KR 컨벤션(빨/파)으로 그려진다
2. 거래량 + 20MA가 하단에 보인다
3. SMA 5/20/60/120 4선이 보인다
4. 일/주/월 탭이 동작하고 줌 시점이 유지된다
5. OHLC 헤더가 호버에 따라 갱신된다
6. BUY/SELL/HOLD 마커와 평단가 라인이 보인다
7. 보조지표 팝오버에서 EMA/Bollinger/RSI/Stoch 토글이 즉시 반영된다
8. 마우스 휠 줌, 드래그 팬, 더블클릭 리셋이 동작한다

---

## Self-Review

**Spec coverage:**
- § 4.1 PricePoint 스키마 → Task 1 ✓
- § 4.2 `_select_ticker_ohlcv` + `_row_is_valid` + 메인 루프 → Task 2-3 ✓
- § 4.5 days 90 → 365 → Task 15 ✓
- § 5.1 의존성 → Task 5 ✓
- § 5.2 컴포넌트 트리 → Task 10-15 ✓
- § 5.3 CandleChart props → Task 10, 11, 14 ✓
- § 5.4 차트 init + panes → Task 10-11, 14 ✓
- § 5.4.1 series-builder → Task 14 ✓
- § 5.5 resample + bucketKey → Task 7-8 ✓
- § 5.6 SMA → Task 11 ✓
- § 5.7 신호 마커 + alignSignals → Task 9, 13 ✓
- § 5.8 OHLC 헤더 → Task 12 ✓
- § 5.9 줌 보존 → Task 11 ✓
- § 5.10 페이지 통합 → Task 15 ✓
- § 6 호환성 (useChartSettings 재사용) → Task 14, 15 ✓
- § 7.1 백엔드 테스트 → Task 2-4 ✓
- § 7.2 프론트 테스트 → Task 7-9, 16 ✓

**Placeholder scan:** "TBD"/"TODO" 없음. 모든 step에 실행 가능한 코드/명령 포함.

**Type consistency:**
- `Interval` 타입은 Task 7에서 정의되어 8/9/10/11에서 일관되게 사용.
- `SignalMarker`는 Task 15에서 새 위치(`candle-chart/types.ts`)로 이동, 모든 import 경로 갱신 명시.
- `OptionalSeries`/`EMPTY_OPTIONAL`은 Task 14에서 정의/export.
- `CHART` 색상 상수는 Task 10에서 정의, 11/12/13/14에서 사용.
- `bucketKey`/`resample`/`alignSignals`는 모두 `resample.ts`에서 export, `candle-chart/index.ts` 또는 직접 상대 경로로 import.

---

## 실행 옵션

Plan complete and saved to `docs/superpowers/plans/2026-05-10-portfolio-candle-chart.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Task별 fresh subagent + 사이사이 코드 리뷰. 빠른 반복.

**2. Inline Execution** — 현재 세션에서 executing-plans로 배치 실행 + 체크포인트.

Which approach?
