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

```python
# 다중 컬럼을 한 번에 추출
need = ["Open", "High", "Low", "Close", "Volume"]
if not all(c in df.columns for c in need):
    # 방어적 폴백: 누락 시 빈 응답으로 처리, 로그 1회
    ...
sub = df[need]
for ts, row in sub.iterrows():
    points.append(PricePoint(
        date=ts.date(),
        open=float(row["Open"]),
        high=float(row["High"]),
        low=float(row["Low"]),
        close=float(row["Close"]),
        volume=int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
    ))
last_close = points[-1].close if points else None
```

**교차오염 방어**: 기존 `key[0] in close_col.columns` 체크는 다중 컬럼 추출에도 동일하게 적용. `df["Close"]`가 멀티컬럼 프레임이면 모든 컬럼(`Open`/`High`/`Low`/`Volume`)이 같은 형태일 가능성이 높으므로 한 번에 ticker 컬럼으로 좁힌다.

**캐시**: 키(`(ticker, days)`)·TTL(300s)·`_CACHE` 구조 모두 그대로. 응답 페이로드만 커진다(필드 5배).

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
export function resample(daily: PricePoint[], unit: "1W" | "1M"): PricePoint[] {
  // 그룹 키:
  //   주: 해당 주의 월요일 ISO 날짜 (date-fns startOfISOWeek)
  //   월: YYYY-MM-01
  // 각 그룹에서:
  //   open  = 첫 거래일 open
  //   close = 마지막 거래일 close
  //   high  = max(high)
  //   low   = min(low)
  //   volume= sum(volume)
}
```

테스트 케이스: 임의 OHLCV 30일 → 주봉 5개로 압축, 각 봉 OHLCV 검증. 빈 입력 / 1일만 있는 입력 / 주말 결손 데이터 엣지 케이스.

### 5.6 SMA 4종 계산

`web/lib/indicators.ts`의 기존 `sma(closes, period)` 함수 그대로 사용. 4번 호출(period=5/20/60/120). 데이터 부족 구간은 `null` → Lightweight Charts에 `whitespace`로 전달.

### 5.7 신호 마커

Lightweight Charts `setMarkers` API로 변환. 기존 `SignalMarker` 인터페이스 유지. 매핑:

| decision | position | shape | color |
|---|---|---|---|
| BUY / OVERWEIGHT | `belowBar` | `arrowUp` | `CHART.up` (#F04452) |
| SELL / UNDERWEIGHT | `aboveBar` | `arrowDown` | `CHART.down` (#1B64DA) |
| HOLD | `inBar` | `circle` | `CHART.hold` (#8B95A1) |

기존 `signals` 계산 로직(`page.tsx:26-42`) 그대로 두고 매퍼만 추가.

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
- yfinance가 OHLCV 5컬럼을 주는 mock 응답 → `PriceHistoryResponse.points[0]`에 5개 필드 모두 채워졌는지.
- Volume이 NaN인 행 → `volume=0`으로 정규화.
- 멀티컬럼 프레임에서 다른 ticker 컬럼 누락 시 폐기 동작이 동일하게 유지되는지(교차오염 방어 회귀 보존).
- 캐시 동작(첫 호출 yfinance 다운로드, 두 번째는 캐시 히트).

### 7.2 프론트

- `resample.ts` 단위 테스트: 일봉 30개 → 주/월 변환 OHLCV 정확성, 빈 입력, 단일 봉, 결손 데이터.
- `CandleChart` 시각 회귀: Playwright 스냅샷 1장(일봉 모드, 평단가 라인 포함, 마커 1개). 인터벌 탭 클릭 → 시리즈 갱신만 확인(픽셀 단위 비교는 불안정하므로 DOM 어설션 위주).
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
