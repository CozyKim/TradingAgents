# 한글/영문 통합 티커 검색 설계

- **작성일**: 2026-05-05
- **대상 영역**: `web/` (Next.js 프론트엔드)
- **상태**: 설계 승인됨 — 구현 플랜 작성 대기

## 1. 배경 및 목표

현재 TradingAgents Web에는 세 곳의 티커 입력 폼이 있다.

- 분석 실행: `web/components/run/run-form.tsx`
- 포트폴리오 보유 추가: `web/components/portfolio/holding-form.tsx`
- 스케줄 생성: `web/components/schedules/schedule-form.tsx`

세 폼 모두 자동완성 없이 단순 텍스트 입력만 받으며, 사용자는 영문 티커(`AAPL`, `GOOGL`)를 정확히 알아야 한다. 한국어 사용자에게 친숙한 한글명(예: `알파벳A`, `애플`, `테슬라`)으로도 티커를 찾을 수 있게 하여 입력 편의성을 높이는 것이 목표다.

### 비목표 (Non-goals)

- 한국 주식, 홍콩/일본 등 비미국 시장은 v1 범위 밖
- 한글 자모 분리/초성 검색(예: `ㅇㅍㅂ` → `알파벳`)은 v1 범위 밖
- 시세/기업 정보 자체 표시는 v1 범위 밖 (검색 결과에는 티커/회사명/한글 별칭만 노출)
- 시가총액·인기도 가중치 기반 정렬은 v1 범위 밖

## 2. 데이터: 티커 시드

### 2.1 위치 및 구조

- 파일: `web/lib/ticker-aliases.ts` (TypeScript, 정적 시드)
- 타입:

```ts
export type TickerEntry = {
  ticker: string;       // "GOOGL"
  name: string;         // "Alphabet Inc. Class A"
  aliases: string[];    // ["알파벳A", "구글A", "구글", "알파벳"]
};

export const TICKER_SEED: readonly TickerEntry[] = [/* ... */];
```

- TS로 정의하는 이유: 컴파일 타임 타입 검증, 트리쉐이킹, 중복 정의 검증 용이.

### 2.2 시드 범위

- S&P 500 + 나스닥 100 + 자주 쓰는 ETF/한국인 보유 미국 종목 → 약 500개 영문 티커 기준.
- 중복 제거 후 단일 목록.

### 2.3 시드 생성 절차

1. 영문 티커/회사명 리스트 확보(공개 데이터셋, yfinance 등으로 일회성 추출).
2. 일회성 스크립트 `scripts/generate-ticker-aliases.ts` (또는 Python `scripts/generate_ticker_aliases.py`)에서:
   - 영문 시드 입력
   - Codex(`/codex:rescue` 또는 동등한 위임)에 "한국 증권사에서 통용되는 한글 표기/별칭" 일괄 생성 요청
   - 결과 JSON을 사람이 검토 후 `ticker-aliases.ts` 형태로 저장
3. 결과는 정적으로 커밋. 런타임에 LLM을 호출하지 않는다.

### 2.4 별칭 정의 가이드라인

- **표준 표기**: 한국 주요 증권사(토스증권, 한국투자증권 등)의 미국 주식 거래 화면에서 쓰는 표기를 우선.
- **클래스 구분**: A/C주가 따로 상장된 종목(예: GOOGL/GOOG)은 한글에도 클래스 표기를 포함(`알파벳A`, `알파벳C`).
- **중복 별칭 허용**: 같은 별칭이 여러 티커에 매칭되어도 무방(예: `구글` → GOOGL, GOOG 둘 다). 검색 결과에서 둘 다 노출.

## 3. 검색 로직

### 3.1 위치 및 API

- 파일: `web/lib/ticker-search.ts` (순수 함수)
- 공개 API:

```ts
export type SearchResult = {
  ticker: string;
  name: string;
  matched: "ticker" | "name" | "alias";  // 매치된 필드
  matchedText?: string;                  // 어떤 별칭/이름에 매치됐는지(UI 강조용)
  score: number;                         // 정렬용 (큰 값이 우선)
};

export function searchTickers(
  query: string,
  options?: { limit?: number; seed?: readonly TickerEntry[] }
): SearchResult[];
```

### 3.2 매칭 규칙 (점수 내림차순)

1. **티커 정확일치**: `GOOGL` → `GOOGL` (최고 점수)
2. **티커 prefix**: `goo` → `GOOGL`, `GOOG`
3. **별칭/회사명 정확일치**: `알파벳A` → `GOOGL`
4. **별칭/회사명 prefix**: `알파` → `GOOGL`
5. **별칭/회사명 substring**: `벳A` → `GOOGL`, `alphabet` → `GOOGL`

동점 처리: `TickerEntry` 시드 정의 순서를 사용(시드 작성 시 자주 쓰는 종목을 위쪽에 배치하면 자연스럽게 우선 노출).

### 3.3 정규화

- 입력: `trim()`, 영문 부분은 `toLowerCase()`로 비교
- 한글: 유니코드 정규화(NFC) 후 그대로 비교
- 자모 분리/초성 검색은 적용하지 않음

### 3.4 기본 옵션

- `limit`: 10
- 빈/공백 입력 → 빈 배열

### 3.5 테스트

- 위치: `web/lib/ticker-search.test.cjs` (기존 `web/lib/indicators.test.cjs` 패턴)
- 케이스:
  - `GOOGL`, `googl`, `Goo` → 티커 정확/prefix 매칭
  - `알파벳A` → 별칭 정확일치
  - `알파` → 별칭 prefix
  - `벳A` → 별칭 substring
  - `alphabet`, `apple` → 영문 회사명 substring
  - `테슬` → TSLA prefix
  - 빈 문자열, 매치 없는 입력 → 빈 배열
  - 우선순위(정확일치가 prefix보다 위) 검증

## 4. 공용 UI 컴포넌트: `<TickerCombobox>`

### 4.1 위치 및 인터페이스

- 파일: `web/components/ui/ticker-combobox.tsx`
- Props:

```ts
type TickerComboboxProps = {
  value: string;
  onChange: (ticker: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
  disabled?: boolean;
  autoFocus?: boolean;
  className?: string;
};
```

### 4.2 구성 요소

- 기존 `Input` 컴포넌트 + Radix `Popover`(`PopoverAnchor`로 입력란을 anchor로 고정) + 결과 리스트.
- 입력 시 `searchTickers(value)` 호출 → 결과가 1개 이상이면 popover 열림, 없으면 닫힘.
- 결과 항목 표기:
  ```
  GOOGL    알파벳A · Alphabet Inc.
  ```
  - 티커는 좌측에 굵게(`font-num font-bold`)
  - 우측에 매치된 별칭/이름과 영문 회사명
  - 매치 부분은 `<mark>` 또는 굵게 강조

### 4.3 인터랙션

- 키보드: `↑/↓` 항목 이동, `Enter` 선택, `Esc` 닫기, `Tab` 닫고 다음 필드로 이동
- 마우스: 항목 클릭 선택, 외부 클릭 시 닫힘
- 선택 시: `onChange(ticker)` 호출 — 항상 영문 대문자 티커로 채움
- **자유 입력 허용**: 매치가 없거나 사용자가 끝까지 직접 친 경우 → 입력값을 정규화(영문은 대문자, 한글은 그대로)하여 `onChange`로 전달, popover 닫힘. 폼 제출 가능.

### 4.4 대문자화

- 영문 자유 입력은 컴포넌트 내부에서 `onChange` 직전에 `toUpperCase()` 적용 (현재 RunForm/HoldingForm이 부모에서 하던 동작을 컴포넌트 안으로 이동).
- 한글 입력은 그대로 둔다(검색 매칭에 필요).

### 4.5 의존성 / 접근성

- 기존 `@radix-ui/react-popover`만 사용. `cmdk` 등 추가 라이브러리 도입 없음.
- ARIA: `role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, 항목에 `role="option"`.

## 5. 폼 통합

### 5.1 RunForm

- `web/components/run/run-form.tsx`의 티커 `<Input>`을 `<TickerCombobox>`로 교체.
- 기존 제출 시 `.toUpperCase()` 호출 유지(컴포넌트가 이미 대문자로 보내지만 안전성 차원).

### 5.2 HoldingForm

- `web/components/portfolio/holding-form.tsx`의 티커 `<Input>` 교체.
- 기존 `onChange` 콜백 내부의 `e.target.value.toUpperCase()`는 컴포넌트가 책임지므로 제거.

### 5.3 ScheduleForm — 칩 UX 리팩터링

- `web/components/schedules/schedule-form.tsx`는 현재 `comma or space separated` 단일 텍스트 영역.
- 변경:
  - 폼 상태: `tickers: string[]` (현재 문자열에서 split하던 로직 제거)
  - UI: `<TickerCombobox>` 1개 + 선택 또는 Enter 시 칩으로 추가
  - 칩 리스트는 입력란 위(또는 아래)에 표시. 각 칩에 ✕ 버튼으로 제거.
  - 빈 입력에서 Backspace 누르면 마지막 칩 제거(선택사항).
  - 자유 입력도 Enter로 추가(시드 미존재 티커 보존).
- 제출 로직: 기존 split 후 forEach로 schedule을 만들던 로직을 `tickers` 배열로 직접 사용.

## 6. 검증

### 6.1 자동

- 유닛 테스트: `node web/lib/ticker-search.test.cjs` (기존 `web/lib/indicators.test.cjs`와 동일 실행 방식)
- 타입 체크: `cd web && npm run typecheck`

### 6.2 수동(브라우저)

- `./dev.sh`로 dev 서버 가동
- 세 폼 각각에서:
  - 한글 검색(`알파`, `테슬`, `애플`) 결과/선택 동작
  - 영문 검색(`googl`, `Goo`, `aapl`) 결과/선택 동작
  - 시드 미존재 티커(`MSTR` 등) 자유 입력 후 제출 가능 여부
  - 키보드 ↑↓/Enter/Esc 동작
- 모바일 뷰포트(Chrome DevTools): popover 위치, 가상 키보드 위에서의 가시성

## 7. 작업 순서

1. 시드 생성 스크립트 작성 → Codex로 한글 별칭 일괄 생성 → `web/lib/ticker-aliases.ts` 커밋
2. `web/lib/ticker-search.ts` + 테스트 작성
3. `web/components/ui/ticker-combobox.tsx` 작성
4. RunForm, HoldingForm 통합
5. ScheduleForm 칩 UX 리팩터링
6. 타입체크 + 수동 브라우저 검증

## 8. 결정 요약

| # | 결정 | 근거 |
|---|------|------|
| 1 | 세 폼 모두 + 공용 컴포넌트 | 일관성, 재사용 |
| 2 | 미국 주식만 (v1) | 사용 빈도, 데이터 단순성. 추후 확장 가능 |
| 3 | 정적 시드 JSON/TS (외부 API 없음) | 한글 검색 가능한 외부 API 부재, 결정적 동작 |
| 4 | 시드 생성에 Codex 위임 | 일회성 작업이라 자동화 효율 |
| 5 | 인라인 popover autocomplete | 친숙한 UX, 기존 popover 컴포넌트 재사용 |
| 6 | 자유 입력 허용 | 시드 누락 종목 차단 시 UX 저하. yfinance가 백엔드 검증 |
