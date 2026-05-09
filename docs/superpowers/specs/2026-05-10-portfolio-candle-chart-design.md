# 포트폴리오 캔들 차트 — 설계 스펙

- 작성일: 2026-05-10
- 대상: `web/components/portfolio/*` + `tradingagents_web/{schemas,services}/price*` 일부

## 1. 목적

포트폴리오 종목 상세 화면(`/portfolio/[ticker]`)의 차트를 TradingView 스타일 캔들 + 거래량 차트로 교체한다. 현재는 종가만 잇는 라인차트(Recharts)라 시세 변동의 분포·추세 인지가 약하고, 사용자가 직접 줌/팬을 할 수 없다. 시각 품질과 인터랙션을 한꺼번에 끌어올린다.

## 2. 현재 상태

- **백엔드**: `tradingagents_web/services/prices.py:97-99` — yfinance에서 OHLCV 전체를 받아 놓고 `Close`만 잘라 `PricePoint(date, close)`로 응답. Open/High/Low/Volume은 버려진다.
- **프론트**: `web/components/portfolio/price-chart.tsx` — Recharts `LineChart`. 종가 라인 + SMA/EMA/Bollinger 오버레이 + 평단가 `ReferenceLine` + BUY/SELL/HOLD `ReferenceDot`. 줌/팬 없음. 인터벌 선택 없음(고정 90일).
- **하위 패널**: `web/components/portfolio/indicator-panel.tsx` — RSI/Stoch 별도 Recharts 패널.

## 3. 브레인스토밍에서 확정된 결정

1. **라이브러리**: TradingView Lightweight Charts(OSS). 캔들/거래량/크로스헤어/줌·팬을 자체 구현하지 않고 라이브러리 기본 동작에 위임.
2. **인터벌 탭**: `일 / 주 / 월` 3개. 분봉/연봉은 비범위.
3. **요소 구성**: 캔들 + 거래량 패널(20MA) + SMA 5/20/60/120 오버레이 + OHLC 헤더 + 우측 현재가 라벨 + BUY/SELL/HOLD 마커 + 평단가 라인.
4. **기존 지표 토글 제거**: EMA / Bollinger / RSI / Stoch UI는 새 차트에서 빠진다. 코어 라이브러리 함수(`web/lib/indicators.ts`)는 보존(미래 재사용 + 평균선 계산 등에 일부 사용).
5. **줌/팬**: Lightweight Charts 기본 동작(휠/드래그/더블클릭 리셋/터치 핀치)을 그대로 활성화.
6. **백엔드 OHLCV 노출**: yfinance가 이미 주는 데이터를 스키마에 펴서 노출. 캐시 키/TTL은 유지.

## 4. 백엔드 변경

### 4.1 스키마 (`tradingagents_web/schemas/price.py`)

```python
class PricePoint(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int  # int로 정규화. yfinance는 float로 주지만 정수가 의미상 옳다.
```

`PriceHistoryResponse`는 그대로(`ticker`, `points`, `last_close`).

### 4.2 서비스 (`tradingagents_web/services/prices.py`)

**OHLCV 추출 헬퍼**:

```python
import math
import pandas as pd

OHLCV_FIELDS: tuple[str, ...] = ("Open", "High", "Low", "Close", "Volume")

def _select_ticker_ohlcv(df: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """Return a flat-column OHLCV frame for `ticker`, or None if unrecoverable.

    Handles both yfinance return shapes:
      - flat columns: ["Open","High","Low","Close","Volume"]
      - MultiIndex columns: [(field, ticker), ...]

    Defense-in-depth: if `multi_level_index=False` is silently ignored by a
    future yfinance version, this still rejects cross-ticker contamination
    instead of returning the first column blindly.
    """
    if df is None or len(df) == 0:
        return None

    # Case 1: flat columns. Verify the full OHLCV set is present.
    if all(f in df.columns for f in OHLCV_FIELDS):
        # Some accessors (df["Close"]) can still be a DataFrame if the underlying
        # frame is multi-ticker. Reject any column whose accessor isn't a Series.
        for f in OHLCV_FIELDS:
            col = df[f]
            if hasattr(col, "columns"):
                if ticker in col.columns:
                    df = df.assign(**{f: col[ticker]})
                else:
                    logger.warning(
                        "prices: %s missing from %s column for %s; aborting",
                        ticker, f, list(col.columns),
                    )
                    return None
        return df[list(OHLCV_FIELDS)]

    # Case 2: MultiIndex (field, ticker). Some yfinance versions still produce
    # this even with multi_level_index=False. Pull the requested ticker out.
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


def _row_is_valid(row: pd.Series) -> bool:
    """All OHLC fields must be finite. Volume may be NaN (treated as 0)."""
    for f in ("Open", "High", "Low", "Close"):
        v = row[f]
        if not pd.notna(v) or not math.isfinite(float(v)):
            return False
    return True
```

**메인 루프**:

```python
sub = _select_ticker_ohlcv(df, key[0])
points: list[PricePoint] = []
last_close: float | None = None
if sub is not None:
    for ts, row in sub.iterrows():
        if not _row_is_valid(row):
            continue  # NaN/inf OHLC가 섞인 행은 통째로 스킵
        vol_raw = row["Volume"]
        volume = (
            int(vol_raw)
            if pd.notna(vol_raw) and math.isfinite(float(vol_raw))
            else 0
        )
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

**캐시**: 키(`(ticker, days)`)·TTL(300s)·`_CACHE` 구조 모두 그대로. 응답 페이로드만 커진다(필드 5배). 빈 응답 캐싱은 기존 동작과 동일(전부 스킵된 경우 빈 points로 캐시 — TTL 안에 자가 회복은 없으나 yfinance 호출량 폭주 방어가 우선).

**Pydantic 검증**: `PricePoint`는 기본 float 검증만 한다. NaN/inf 차단은 위 `_row_is_valid`에서 한 번만 수행하므로 PricePoint 생성 시점에 비정상 값이 들어올 일이 없다. (Pydantic v2의 strict 모드에서도 `float('nan')`은 통과하므로 서비스 레이어에서 막는 것이 옳음.)

### 4.3 API 라우트

`tradingagents_web/api/prices.py`는 변경 없음(스키마가 자동으로 응답에 반영됨).

### 4.4 인터벌 처리

- 백엔드는 **일봉만** 보낸다(`days=180` 정도로 늘릴 가능성 있음, 4.5 참고).
- 주봉/월봉은 프론트에서 일봉을 리샘플링한다(§ 5.5). 백엔드에 인터벌 파라미터를 넣지 않는다.

### 4.5 데이터 윈도우

- 현재 `days=90`(`web/app/(workspace)/portfolio/[ticker]/page.tsx:20`).
- 새 차트에서 월봉을 의미 있게 보려면 90일은 짧다. **`days=365`로 확장**(약 1년 ≈ 52주봉 ≈ 12월봉).
- `usePriceHistory(ticker, 365)`로 호출 인자만 변경. 백엔드는 days를 그대로 yfinance에 전달하므로 추가 변경 없음.

## 5. 프론트엔드 변경

### 5.1 의존성

```bash
pnpm --dir web add lightweight-charts
```

번들 크기: 약 50KB gzipped. Recharts(이미 설치됨)는 다른 화면(대시보드 등)에서 계속 사용하므로 제거하지 않는다.

### 5.2 새 컴포넌트 트리

```
components/portfolio/
├── candle-chart/
│   ├── candle-chart.tsx       — 메인 컴포넌트. 차트 + 거래량 패널 + 오버레이 통합.
│   ├── interval-tabs.tsx      — 일/주/월 탭.
│   ├── ohlc-header.tsx        — 상단 시가/고가/저가/종가/% 표시.
│   ├── resample.ts            — 일봉 → 주봉/월봉 변환.
│   └── series-config.ts       — 색상/스타일 상수(다크/라이트 모드).
├── price-chart.tsx            — (제거) 기존 라인차트.
├── chart-stack.tsx            — (제거) 기존 래퍼.
├── indicator-toolbar.tsx      — (제거)
├── indicator-panel.tsx        — (제거)
└── indicator-colors.ts        — (보존, 일부 색상은 series-config로 마이그레이션)
```

### 5.3 `CandleChart` 컴포넌트 인터페이스

```ts
interface CandleChartProps {
  points: PricePoint[];           // 일봉 OHLCV (백엔드 응답)
  signals?: SignalMarker[];        // BUY/SELL/HOLD 마커
  avgCost?: number;                // 평단가 라인
  initialInterval?: "1D" | "1W" | "1M";
  height?: number;                 // 기본 480
}
```

내부 상태:
- `interval` — 현재 선택 탭. 변경 시 `resample`로 시리즈 재계산, 줌 상태는 보존(`timeScale().getVisibleLogicalRange()`로 저장 후 새 데이터에 매핑하여 복원).
- `hovered` — 크로스헤어 위치의 OHLC. `chart.subscribeCrosshairMove`로 업데이트, OHLC 헤더에 표시.

### 5.4 Lightweight Charts 구성

**테마 정합성**: 프로젝트는 토스 스타일 라이트 모드이며 KR-시장 색상(상승=빨강 `#F04452`, 하락=파랑 `#1B64DA`)을 사용한다(`tailwind.config.ts:30-32` `signal.buy/sell/hold`). 새 차트도 라이트 테마를 유지하고, 캔들 색상만 KR 컨벤션을 따른다(스크린샷의 다크 배경은 모방하지 않는다 — 페이지 전반과 시각적 충돌).

`series-config.ts`에서 색을 한 곳에 모은다:
```ts
export const CHART = {
  up: "#F04452",         // signal.buy
  down: "#1B64DA",       // signal.sell
  hold: "#8B95A1",       // text-3
  axis: "#C0C8CF",       // border-2
  grid: "#EAECEF",       // border-1
  text: "#4E5968",       // text-2
  background: "#FFFFFF", // bg-1 (카드 위)
  ma5: "#F59E0B",        // 기존 INDICATOR_COLORS.sma 재사용
  ma20: "#06B6D4",
  ma60: "#7C3AED",
  ma120: "#8B95A1",
  volumeUp: "rgba(240, 68, 82, 0.45)",
  volumeDown: "rgba(27, 100, 218, 0.45)",
  volumeMa: "#3182F6",   // accent
  avgCost: "#8B95A1",
} as const;
```

```ts
const chart = createChart(containerRef.current, {
  layout: { background: { color: CHART.background }, textColor: CHART.text },
  grid: { vertLines: { color: CHART.grid }, horzLines: { color: CHART.grid } },
  crosshair: { mode: CrosshairMode.Normal },
  rightPriceScale: { borderColor: CHART.axis },
  timeScale: { borderColor: CHART.axis, timeVisible: false },
});

const candleSeries = chart.addCandlestickSeries({
  upColor: CHART.up, downColor: CHART.down,
  borderUpColor: CHART.up, borderDownColor: CHART.down,
  wickUpColor: CHART.up, wickDownColor: CHART.down,
});

// SMA 4종 (5/20/60/120) — addLineSeries 4회 (CHART.ma5/ma20/ma60/ma120)
// 거래량 패널 — addHistogramSeries({ priceScaleId: "vol" }) + 별도 priceScale 영역(0~30%)
// 거래량 20MA — addLineSeries({ priceScaleId: "vol" })
// 평단가 — candleSeries.createPriceLine({ price: avgCost, color: CHART.avgCost, lineStyle: 2 })
// 신호 마커 — candleSeries.setMarkers([{ time, position, shape, color, text }])
```

다크 모드 전환은 비범위(프로젝트 전체가 라이트 모드 전제). 추후 다크 모드 도입 시 CSS 변수로 추출하고 `chart.applyOptions(...)`로 재적용한다.

### 5.5 일봉 → 주봉/월봉 리샘플링 (`resample.ts`)

```ts
export type Interval = "1D" | "1W" | "1M";

/** 일봉 날짜 문자열을 주/월 bucket의 대표 날짜(`YYYY-MM-DD`)로 변환. */
export function bucketKey(date: string, interval: Interval): string {
  if (interval === "1D") return date;
  if (interval === "1W") {
    // 해당 주의 월요일 ISO 날짜 (date-fns startOfISOWeek)
    ...
  }
  // "1M": YYYY-MM-01
  return date.slice(0, 7) + "-01";
}

export function resample(daily: PricePoint[], interval: Interval): PricePoint[] {
  if (interval === "1D") return daily;
  // bucketKey로 그룹핑 → 각 그룹에서:
  //   open  = 첫 거래일 open
  //   close = 마지막 거래일 close
  //   high  = max(high)
  //   low   = min(low)
  //   volume= sum(volume)
}
```

**`bucketKey`는 `alignSignals`(§ 5.7)와 공유**되어야 한다. 캔들과 마커의 time key 일관성이 깨지면 마커가 사라진다.

테스트 케이스:
- `bucketKey`: 1D 항등, 1W는 화/수/목/금/일·월 모두 같은 월요일로 매핑, 1M은 `2026-04-29 → 2026-04-01`. ISO 주(월요일 시작) 가정 명시.
- `resample`: 임의 OHLCV 30일 → 주봉 5개로 압축, 각 봉 OHLCV 검증. 빈 입력 / 1일만 있는 입력 / 주말 결손 데이터 엣지 케이스.
- **회귀**: `bucketKey`가 캔들과 신호에 동일하게 적용되는지(같은 date 입력 → 같은 출력) 단위 테스트.

### 5.6 SMA 4종 계산

`web/lib/indicators.ts`의 기존 `sma(closes, period)` 함수 그대로 사용. 4번 호출(period=5/20/60/120). 데이터 부족 구간은 `null` → Lightweight Charts에 `whitespace`로 전달.

### 5.7 신호 마커

Lightweight Charts `setMarkers` API로 변환. 기존 `SignalMarker` 인터페이스 유지. 매핑:

| decision | position | shape | color |
|---|---|---|---|
| BUY / OVERWEIGHT | `belowBar` | `arrowUp` | `CHART.up` (#F04452) |
| SELL / UNDERWEIGHT | `aboveBar` | `arrowDown` | `CHART.down` (#1B64DA) |
| HOLD | `inBar` | `circle` | `CHART.hold` (#8B95A1) |

**인터벌별 시각 시간 정렬(critical)**: `signals[i].date`는 항상 일봉 기준 `analysis_date`다. 인터벌이 주/월로 바뀌면 캔들의 time key는 해당 주의 월요일 / 해당 월의 1일로 옮겨가므로, **마커도 같은 bucket key로 매핑하지 않으면 마커가 차트에서 사라지거나 잘못된 캔들 위에 놓인다**. 이 변환은 `resample.ts`와 같은 bucket 함수를 공유한다:

```ts
import { bucketKey, type Interval } from "./resample";

function alignSignals(
  signals: SignalMarker[],
  interval: Interval,
): SignalMarker[] {
  if (interval === "1D") return signals;
  // bucket → 가장 최신 신호 1개 (Map은 동일 키 덮어쓰기 — 입력이 created_at DESC 정렬이라
  // 가정하고, 최신을 먼저 본 시점에서 잠금. page.tsx:30-42의 seenDates 로직과 동일 정책).
  const out = new Map<string, SignalMarker>();
  for (const s of signals) {
    const k = bucketKey(s.date, interval);
    if (out.has(k)) continue; // 한 bucket의 최신 신호 1개만 유지
    out.set(k, { ...s, date: k });
  }
  return [...out.values()];
}
```

**정책**: 한 bucket(주/월) 안에 여러 결정이 있으면 **최신 1개만 표시**. 누적 마커는 차트를 노이즈로 만들고, 마커 색이 BUY와 SELL이 섞이면 의미 전달이 무너진다. 이 정책은 일봉 모드의 `seenDates` 로직(같은 날짜에 최신만)과 일관된다.

**테스트**: 인터벌 탭 전환 후 마커가 사라지지 않고 같은 캔들 위치에 일대일 대응으로 남아 있는지 확인하는 단위 테스트(`alignSignals`) + Playwright DOM 어설션(주봉 모드에서도 마커 SVG 노드가 N개 존재).

### 5.8 OHLC 헤더

스크린샷 상단 바와 동일한 레이아웃:
```
시가 1,295,000원 (+0.54%)  고가 1,317,000원 (+2.25%)  저가 1,274,000원 (-1.08%)  종가 1,300,000원 (+0.93%)
```
- 변동률 기준: 직전 봉 종가 대비 (close[i-1] → 현재 봉 OHLC).
- 호버 중이면 호버 봉, 아니면 마지막 봉.
- `formatPrice`(통화 컨텍스트 인지)로 포맷팅. 등락 색은 KR 컨벤션 — 양수 = `text-signal-buy`(빨강), 음수 = `text-signal-sell`(파랑), 0 = `text-text-3`. (참고: 기존 코드 `text-pos`/`text-neg` 클래스는 Tailwind 설정에 정의되지 않은 미적용 클래스이므로 사용하지 않는다.)

### 5.9 줌 상태 보존

```ts
const range = chart.timeScale().getVisibleLogicalRange();
// interval 변경 → 시리즈 setData → ...
chart.timeScale().setVisibleLogicalRange(range);
```
일↔주↔월 사이에서 봉 개수가 바뀌므로 logical range를 그대로 적용하면 시점이 어긋난다. **시점 보존이 더 정확한 UX이므로** `getVisibleRange()`(time-based) 결과를 저장 후 그대로 `setVisibleRange()`로 복원한다.

### 5.10 페이지 통합 (`/portfolio/[ticker]/page.tsx`)

변경:
- `usePriceHistory(ticker, 90)` → `usePriceHistory(ticker, 365)`.
- `<ChartStack ... />` → `<CandleChart points={price?.points ?? []} signals={signals} avgCost={holding?.avg_cost} />`.
- `useChartSettings`/`reset` 호출 제거.
- 카드 헤더 "Price (90d)" → "Price".

## 6. 호환성/마이그레이션

- `useChartSettings` 훅과 `lib/chart-settings.ts`: 새 차트가 사용하지 않음. 다른 화면이 사용하지 않는다면 함께 삭제(검색 후 결정). `localStorage` 키도 정리.
- `web/components/dashboard/portfolio-signals.tsx`: 별도 컴포넌트 — 영향 없음.
- 테스트: `tests/web/test_runner_fake.py` 등 백엔드 테스트는 PricePoint 변경에 영향. 픽스처/모킹 업데이트 필요.

## 7. 테스트 계획

### 7.1 백엔드

`tests/web/test_prices_service.py`(기존 갱신) + `tests/web/test_prices_api.py`(필요 시 응답 스냅샷 갱신):

**기본 동작**:
- yfinance가 OHLCV 5컬럼(flat)을 주는 mock 응답 → `PriceHistoryResponse.points[0]`에 5개 필드 모두 채워졌는지, `last_close`가 마지막 valid 행과 일치하는지.
- 캐시 동작(첫 호출 yfinance 다운로드, 두 번째는 캐시 히트).

**OHLC 정규화 회귀(critical)**:
- Volume이 NaN인 행 → `volume=0`으로 정규화, 다른 필드는 그대로 보존.
- Open/High/Low/Close 중 하나라도 NaN이거나 ±inf → 해당 행은 통째로 스킵(다른 행은 정상 포함).
- 모든 행이 invalid → 빈 `points`, `last_close=None` 반환(예외 없음).
- `last_close`가 마지막 invalid 행이 아니라 마지막 **valid** 행 기준임을 단위 테스트로 확인.

**MultiIndex/교차오염 방어(critical)**:
- flat 컬럼이지만 일부 컬럼(`df["Open"]`)이 다중 ticker DataFrame인 경우 — 요청 ticker 존재 시 해당 컬럼만 추출, 없으면 전체 폐기.
- MultiIndex `(field, ticker)` 컬럼 입력 — 요청 ticker가 모든 OHLCV 필드에 존재 → 정상 추출.
- MultiIndex 입력에서 요청 ticker가 누락 → 빈 응답, 다른 ticker 가격 누설 없음.
- MultiIndex 입력에서 일부 필드(예: `Volume`)에만 요청 ticker가 누락 → 빈 응답(부분 데이터 거부).

### 7.2 프론트

- `resample.ts` 단위 테스트(§ 5.5 참고): `bucketKey` 일관성 + 일봉 30개 → 주/월 변환 OHLCV 정확성, 빈 입력, 단일 봉, 결손 데이터.
- `alignSignals` 단위 테스트(§ 5.7 참고): 한 bucket에 신호 N개 → 최신 1개만 유지, date 필드가 bucket key로 교체됨, 일봉 모드는 항등.
- `CandleChart` 시각 회귀: Playwright 스냅샷 1장(일봉 모드, 평단가 라인 포함, 마커 1개). 인터벌 탭 클릭 → 시리즈 갱신만 확인(픽셀 단위 비교는 불안정하므로 DOM 어설션 위주).
- **마커 보존 회귀**: 일봉에서 N개 마커 → 주봉 클릭 → 마커가 0이 되지 않고 N 이하의 유의미한 수로 남는지 DOM 어설션. 한투 차트 대비 우리 시스템 핵심 차별점인 BUY/SELL 표시가 인터벌 전환에서 사라지는 회귀를 막는 것이 목적.
- E2E(`web/tests/e2e/portfolio.spec.ts`): 차트가 렌더되고 인터벌 탭 전환이 에러 없이 동작.

## 8. 비범위 (Out of scope)

- 분봉/연봉 인터벌.
- 그리기 도구(추세선/피보나치 등).
- 종목 비교(여러 ticker 오버레이).
- 차트 풀스크린 모달.
- 보조지표 토글(EMA/Bollinger/RSI/Stoch UI 복귀) — 코어 함수는 보존하되 UI는 빠진다. 사용자가 다시 원할 경우 별도 PR로 부활.
- 실시간 가격 업데이트(WebSocket/폴링).

## 9. 작업 순서(개략)

1. **백엔드 OHLCV** — `schemas/price.py` + `services/prices.py` 수정 + 테스트 갱신.
2. **프론트 의존성** — `lightweight-charts` 추가, `lib/prices.ts`의 `PricePoint` 타입 동기화.
3. **`resample.ts`** — 단위 테스트 우선 작성 후 구현.
4. **`CandleChart` 골격** — 캔들 + 거래량만 먼저, 인터벌 일 고정.
5. **인터벌 탭 + 줌 보존** — 주/월 리샘플링 연결.
6. **OHLC 헤더 + 크로스헤어 동기화**.
7. **SMA 4종 + 거래량 20MA**.
8. **신호 마커 + 평단가 라인**.
9. **페이지 통합 + 기존 컴포넌트 제거**.
10. **시각/E2E 회귀 테스트**.

## 10. 위험·열린 질문

- **번들 크기**: 약 50KB 추가. 포트폴리오 상세에서만 필요하므로 `next/dynamic`으로 lazy-load 검토(SSR 비활성).
- **연 1회 yfinance 변경**: 컬럼명/멀티인덱스 변경 사례가 과거에 있었음. 코드는 이미 멀티컬럼 방어가 있고 새 코드도 동일 구조 따른다.
- **거래량이 0인 종목**: 일부 펀드/ETF는 거래량 NaN/0. 기본값 0으로 안전.
- **`PricePoint` 타입 호환성**: `web/lib/prices.ts`의 프론트 타입이 백엔드와 함께 변경된다. 이 타입을 import하는 다른 위치(`useHoldings`, `dashboard/portfolio-signals`, `lib/indicators` 호출부 등)는 `close` 필드만 사용하므로 영향 없을 가능성이 높지만, 빌드 단계에서 확인.
