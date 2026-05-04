# Currency Toggle (USD/KRW) — Design

**Status**: Draft
**Date**: 2026-05-05
**Author**: jaehyun

## Summary

가격 표시 옆에 통화 단위(`$` / `₩`)를 명시하고, 사이드바/헤더의 토글로 전체 화면 표시 통화를 USD ↔ KRW 사이에서 전환한다. 환율(USD/KRW)은 백엔드가 yfinance `KRW=X`로 하루 1회 갱신해 캐시하고, 프론트엔드는 그 값을 받아 클라이언트 사이드에서 환산만 수행한다.

## Decisions (확정 사항)

| # | 항목 | 결정 |
|---|------|------|
| A1 | 종목 통화 모델 | 모든 종목은 USD 네이티브 (US 주식만 다룸) |
| A2 | 환율 데이터 소스 | yfinance `KRW=X` (Yahoo Finance forex 티커) |
| A3 | 토글 상태 저장소 | `localStorage` (계정/디바이스 동기화 없음) |
| A4 | 토글 적용 범위 | 표시 전용; 입력(`HoldingForm.avg_cost`)은 항상 USD |
| A5 | 토글 UI 위치 | 글로벌 — 데스크톱 사이드바, 모바일 상단 바 |

## Goals / Non-Goals

**Goals**
- 모든 가격 셀 옆에 통화 기호(`$` / `₩`) 표기.
- 한 번의 토글 클릭으로 앱 전역 표시 단위 전환 (네트워크 호출 없이 즉시).
- 환율은 하루 1회 갱신 (백엔드 24h TTL, 프론트 12h staleTime).
- 환율 fetch 실패 시 graceful fallback (USD 고정).

**Non-Goals**
- 다중 통화 지원 (EUR/JPY/CNY 등) — USD ↔ KRW만.
- 인트라데이 환율 (일종가만).
- 사용자별 선호 통화의 DB 저장 / 디바이스 간 동기화.
- KRW 입력 → USD 환산 저장 (환율 변동에 따라 보유 비용이 매일 달라 보이는 UX 회피).
- 환율 히스토리 차트.

## Architecture

USD 네이티브 가격을 DB/API에 그대로 보관하고, **표시 시점**에 토글 상태에 따라 환율을 곱해 환산한다. 환율 fetch와 가격 fetch는 별도 엔드포인트(캐시 정책이 다름).

```
┌──────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                  │
│  ┌──────────────────────────────────────────────┐    │
│  │  CurrencyProvider (React Context)            │    │
│  │   - currency: "USD" | "KRW"   ← localStorage │    │
│  │   - fxRate: { rate, as_of }   ← React Query  │    │
│  │   - toggle()                                 │    │
│  └──────────────────────────────────────────────┘    │
│           ▲                ▲                         │
│  ┌────────┴──────┐  ┌──────┴──────────┐              │
│  │ CurrencyToggle│  │ formatPrice()    │             │
│  │ (사이드바/탭바)│  │ (모든 가격 셀)   │            │
│  └───────────────┘  └─────────────────┘              │
└──────────────────────────────────────────────────────┘
                                │
                                ▼ GET /api/fx/usd-krw
┌──────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                   │
│  ┌──────────────────────────────────────────────┐    │
│  │  services/fx.py                              │    │
│  │   - get_usd_krw_rate()                       │    │
│  │   - in-memory cache, 24h TTL                 │    │
│  │   - yfinance.download("KRW=X", period="5d")  │    │
│  └──────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

## Backend

### `tradingagents_web/schemas/fx.py` (신규)

```python
class FxRate(BaseModel):
    pair: str            # "USDKRW"
    rate: float | None   # 1380.45 — 1 USD = X KRW; null이면 미조회/실패
    as_of: date | None   # 환율 종가 기준일
    fetched_at: datetime # 서버가 fetch한 시각 (디버깅/표시용)
```

### `tradingagents_web/services/fx.py` (신규)

`services/prices.py` 패턴(`_TTL_SECONDS`, `_CACHE`, `_yf_download`)을 그대로 따르되, `_YF_LOCK`은 `prices.py`의 락을 공유 사용한다.

```python
_TTL_SECONDS = 24 * 3600
# (expires_at_unix, FxRate). 단일 통화쌍이라 dict 대신 단일 슬롯.
_CACHE: tuple[float, FxRate] | None = None
# yfinance 직렬화는 services/prices.py의 _YF_LOCK을 공유 사용한다 (yfinance가
# 모듈 단위 thread-unsafe). 별도 락을 두면 동시 호출 시 yfinance 내부 상태 충돌.


def _extract_last_close(df: Any) -> tuple[float | None, date | None]:
    """yfinance DataFrame에서 가장 최근 non-null Close 행을 뽑아낸다."""
    if df is None or len(df) == 0 or "Close" not in df.columns:
        return None, None
    series = df["Close"].dropna()
    if series.empty:
        return None, None
    last_ts = series.index[-1]
    return float(series.iloc[-1]), last_ts.date()


def get_usd_krw_rate() -> FxRate:
    """USD/KRW 환율 종가. 24h TTL 캐시, 실패 시 직전 캐시 반환."""
    now = time.time()
    cached = _CACHE
    if cached and cached[0] > now:
        return cached[1]

    fetched_at = datetime.now(timezone.utc)
    try:
        df = _yf_download("KRW=X", period="5d", interval="1d")
        rate, as_of = _extract_last_close(df)
        result = FxRate(
            pair="USDKRW", rate=rate, as_of=as_of, fetched_at=fetched_at,
        )
    except Exception:
        logger.exception("yfinance KRW=X download failed")
        if cached:
            return cached[1]  # stale 허용 (TTL 초과여도 직전 값이 무응답보다 낫다)
        result = FxRate(
            pair="USDKRW", rate=None, as_of=None, fetched_at=fetched_at,
        )

    _CACHE = (now + _TTL_SECONDS, result)
    return result


def clear_cache() -> None:
    """테스트/설정 리로드용."""
    global _CACHE
    _CACHE = None
```

- `_yf_download`은 `services/prices.py`의 동일 헬퍼를 그대로 import한다 (yfinance는 모듈 단위로 thread-unsafe하므로 동일 락을 공유해야 한다).
- `period="5d"`는 휴장/주말로 당일 종가가 없을 때 직전 영업일 값을 잡기 위한 여유 윈도.
- `_extract_last_close`는 `dropna()`로 결측 처리 — yfinance가 가끔 빈 행을 끼워 넣는 경우 방어.

### `tradingagents_web/api/fx.py` (신규)

```python
router = APIRouter(prefix="/api/fx", tags=["fx"])


@router.get("/usd-krw", response_model=FxRate)
async def usd_krw(
    _user: Annotated[User, Depends(get_current_user)],
) -> FxRate:
    return await asyncio.to_thread(fx_svc.get_usd_krw_rate)
```

`tradingagents_web/main.py`에 `app.include_router(fx_api.router)` 추가.

### 백엔드 테스트 (`tests/test_fx_service.py`)

`_yf_download`을 monkeypatch하여:
1. **정상**: 5일치 DataFrame → 마지막 Close가 `rate`, ts가 `as_of`로 들어감.
2. **캐시 히트**: 두 번째 호출이 `_yf_download`를 다시 부르지 않음.
3. **yfinance 실패 + 캐시 없음**: `rate=None` 반환.
4. **yfinance 실패 + 캐시 있음**: 직전 캐시값을 그대로 반환 (stale).
5. **빈 DataFrame**: `rate=None` 반환.

## Frontend

### `web/lib/fx.ts` (신규)

```ts
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

### `web/hooks/use-fx-rate.ts` (신규)

```ts
export function useFxRate() {
  return useQuery({
    queryKey: ["fx", "usd-krw"],
    queryFn: getUsdKrwRate,
    staleTime: 12 * 60 * 60 * 1000, // 12h — 백엔드 24h의 절반
    refetchOnWindowFocus: false,
  });
}
```

### `web/lib/currency.tsx` (신규 — Provider + 포맷터)

```tsx
type Currency = "USD" | "KRW";

interface CurrencyCtx {
  currency: Currency;
  setCurrency: (c: Currency) => void;
  toggle: () => void;
  fxRate: number | null;   // null이면 KRW 모드 비활성
  fxAsOf: string | null;
  fxLoading: boolean;
}

const STORAGE_KEY = "currency-preference";

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [currency, setCurrencyState] = useState<Currency>("USD");
  const { data, isLoading } = useFxRate();

  // hydrate from localStorage on mount (SSR-safe)
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "USD" || saved === "KRW") setCurrencyState(saved);
  }, []);

  const setCurrency = (c: Currency) => {
    setCurrencyState(c);
    localStorage.setItem(STORAGE_KEY, c);
  };

  const fxRate = data?.rate ?? null;
  const effectiveCurrency = currency === "KRW" && fxRate == null ? "USD" : currency;

  return (
    <CurrencyContext.Provider value={{
      currency: effectiveCurrency,
      setCurrency,
      toggle: () => setCurrency(effectiveCurrency === "USD" ? "KRW" : "USD"),
      fxRate,
      fxAsOf: data?.as_of ?? null,
      fxLoading: isLoading,
    }}>
      {children}
    </CurrencyContext.Provider>
  );
}

export function useCurrency(): CurrencyCtx { ... }

export function formatPrice(
  usdValue: number | null | undefined,
  ctx: Pick<CurrencyCtx, "currency" | "fxRate">,
  opts?: { signed?: boolean; usdDecimals?: number },
): string {
  if (usdValue == null || !Number.isFinite(usdValue)) return "—";

  // 부호는 기호 앞에 붙도록 절댓값으로 분리해 포맷한다.
  // (-$12.34 / +$12.34, -₩17,036 / +₩17,036)
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

### `web/components/nav/currency-toggle.tsx` (신규)

세그먼트 컨트롤 형태:

```
┌─────────────┐
│ USD │  KRW  │   ← active 쪽이 진한 배경
└─────────────┘
   as_of 2026-05-04   ← KRW일 때만 작게 표기
```

- `fxRate == null`일 때: KRW 버튼 disabled + `title`에 `"환율 정보를 불러올 수 없어 KRW 모드를 사용할 수 없습니다"`.
- 데스크톱: `Sidebar` 하단(섹션 그룹 아래) 또는 워크스페이스 헤더 우측(`UnreadBell` 옆) — 구현 시 사이드바 하단 우선.
- 모바일: `MobileTopBar` 우측에 컴팩트 버전.

### 통합 지점

1. **`web/app/(workspace)/layout.tsx`**: `<CurrencyProvider>`로 children 래핑.
2. **`web/components/nav/sidebar.tsx`**: 하단 섹션에 `<CurrencyToggle />` 추가.
3. **`web/components/nav/mobile-top-bar.tsx`**: 헤더 우측에 `<CurrencyToggle />` 추가.
4. **가격 표시 셀 일괄 교체** — 모두 `useCurrency()` + `formatPrice()` 사용:
   - `web/components/portfolio/holdings-table.tsx` — Avg Cost, Last (`h.avg_cost`, `last`)
   - `web/components/portfolio/pnl-cell.tsx` — `pnl` 절댓값 (`pct`는 통화 무관, 그대로 유지)
   - `web/app/(workspace)/portfolio/[ticker]/page.tsx` — Avg cost / Last / P&L 카드
   - `web/components/portfolio/price-chart.tsx`
     - Y축 `tickFormatter`
     - `PriceTooltip` 내부 `fmtPrice`
     - `ReferenceLine` `label.value` (`Avg ${...}`)
5. **`web/components/portfolio/holding-form.tsx`**: Avg cost 라벨에 `(USD)` 명시 (입력은 USD 고정).

### 차트 처리 (중요)

- `LineChart`의 `data.close`, `sma`, `ema`, `bbMid/Up/Lo`는 모두 USD 그대로 유지.
- KRW 모드에서도 **그래프 모양은 동일** (전부 동일 비율로 환산되므로). 표시 함수만 바뀌어 사용자에게 혼동 없음.
- `ReferenceLine y={avgCost}`도 USD 값 그대로; `label.value`만 `formatPrice`로 변환.

### 프론트엔드 테스트 (`web/lib/currency.test.cjs`)

`web/lib/indicators.test.cjs` 패턴 따라:
1. `formatPrice(123.45, {currency:"USD"})` → `"$123.45"`
2. `formatPrice(123.45, {currency:"KRW", fxRate:1380})` → `"₩170,361"` (반올림)
3. `formatPrice(null, ...)` → `"—"`
4. `formatPrice(123.45, {currency:"KRW", fxRate:null})` → 처리: Provider가 `effectiveCurrency`를 USD로 폴백시키므로 호출자 입장에선 USD 분기로 진입 → `"$123.45"`
5. 음수 부호 위치: `formatPrice(-12.34, USD)` → `"-$12.34"` (기호 앞에 부호)
6. `signed:true` + 양수: `formatPrice(12.34, USD, {signed:true})` → `"+$12.34"`
7. `usdDecimals:0` → 소수점 없는 USD 출력

## Data Flow

### 정상 시나리오

1. 첫 페이지 로드 → `<CurrencyProvider>`가 `localStorage["currency-preference"]` 읽음 (없으면 `"USD"`).
2. `useFxRate()`가 `/api/fx/usd-krw` 1회 호출.
3. 백엔드는 24h 캐시에서 즉시 반환 (또는 yfinance 호출 후 캐시).
4. 모든 가격 셀이 `useCurrency()`로 ctx 받아 `formatPrice(value, ctx)` 호출.
5. 토글 클릭 → Context 갱신 → 모든 가격 셀 즉시 리렌더 (네트워크 X).
6. 새로고침해도 localStorage 값 유지.

### 엣지 케이스

| 상황 | 동작 |
|------|------|
| 백엔드 yfinance 실패 + 캐시 없음 | API 응답 `rate: null`. 프론트는 KRW 토글 비활성. |
| 백엔드 yfinance 실패 + 캐시 있음 | API 응답 직전 캐시값 반환 (stale 허용). |
| 프론트 `/api/fx/usd-krw` 호출 실패 | React Query 기본 retry 후 `data: undefined`. KRW 토글 비활성. |
| KRW 모드인데 `fxRate === null` | `effectiveCurrency`가 USD로 자동 폴백 표시. localStorage 값은 유지(다음에 환율 복구되면 자동 KRW). |
| SSR/hydration | 첫 렌더는 항상 `"USD"`로 시작; mount 후 `useEffect`에서 hydrate. |
| 12h staleTime 동안 환율 갱신 | 같은 세션 내 KRW 값이 흔들리지 않음 (안정성 우선). |

## Trade-offs

- **표시 시점 환산 vs API 단 환산**: 표시 시점 환산을 택함. 이유: (1) 가격 데이터는 USD로 일관 보관, (2) 토글이 즉시 반영, (3) 백엔드 응답 캐시(`yfinance` 5분 TTL)와 환율 캐시(24h TTL)를 분리 관리 가능.
- **localStorage vs DB**: localStorage 택함. 이유: 개인용 스케일, 디바이스별 선호가 다를 여지, 스키마 마이그레이션 회피. 향후 다기기 동기화 요구가 생기면 DB로 승격 가능 (Provider 인터페이스만 유지하면 무중단).
- **세그먼트 토글 vs 단일 버튼**: 세그먼트 택함. 이유: 현재 상태가 명시적으로 보이고, 한 번 클릭으로 원하는 통화 선택 가능 (단일 토글은 두 번 눌러야 하는 경우 발생).
- **토글 위치 글로벌 vs 인라인**: 글로벌 택함. 이유: 가격이 여러 화면에 분산되어 있어 한 곳에서 일괄 제어가 자연스러움.

## File Manifest

**신규**
- `tradingagents_web/schemas/fx.py`
- `tradingagents_web/services/fx.py`
- `tradingagents_web/api/fx.py`
- `tests/test_fx_service.py`
- `web/lib/fx.ts`
- `web/lib/currency.tsx`
- `web/lib/currency.test.cjs`
- `web/hooks/use-fx-rate.ts`
- `web/components/nav/currency-toggle.tsx`

**수정**
- `tradingagents_web/main.py` (라우터 등록)
- `web/app/(workspace)/layout.tsx` (Provider 래핑)
- `web/components/nav/sidebar.tsx` (Toggle 배치)
- `web/components/nav/mobile-top-bar.tsx` (Toggle 배치)
- `web/components/portfolio/holdings-table.tsx`
- `web/components/portfolio/pnl-cell.tsx`
- `web/components/portfolio/price-chart.tsx`
- `web/components/portfolio/holding-form.tsx` (라벨에 `(USD)` 명시)
- `web/app/(workspace)/portfolio/[ticker]/page.tsx`

## Open Questions

없음. 모든 결정사항은 위 Decisions 표에 명시.
