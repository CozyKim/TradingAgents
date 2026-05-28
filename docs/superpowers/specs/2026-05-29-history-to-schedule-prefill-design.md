# 히스토리 → 스케줄 빠른 추가 (Design)

- **일자:** 2026-05-29
- **상태:** Approved
- **관련 영역:** `web/components/history`, `web/components/schedules`

## 배경

분석 기록(`/history`)을 둘러보다가 "이 종목은 앞으로도 매일 자동 분석하고
싶다"는 충동이 생겨도, 현재는 `/schedules/new`로 직접 이동해서 ticker를
다시 입력해야 한다. 한 번 더 손이 가는 마찰을 없애기 위해, 히스토리 행에서
한 번의 클릭으로 해당 ticker가 prefill된 스케줄 생성 화면으로 진입할 수
있도록 한다.

## 목표

- 히스토리 테이블의 각 행에서 단일 클릭으로 "이 종목 트래킹 추가" 흐름을
  시작할 수 있다.
- 클릭 후에는 ScheduleForm 위에 분석 기록과의 연결이 시각적으로 드러난다.
- 기존 `/schedules/new`의 입력 항목(cron, analysts, rounds 등)은 사용자가
  여전히 통제한다 — prefill은 ticker만 한다.

## 비목표 (Out of Scope)

- 히스토리 다중 선택 → 일괄 스케줄 생성. 기존 ScheduleForm은 다중 ticker를
  하나의 cron으로 묶어 생성하지만, 히스토리에서의 일괄 선택 → 일괄 추가
  UX는 별도 작업으로 분리한다.
- 분석 시점의 analysts/rounds 자동 복제. `RunListItem`에는 해당 필드가
  없고 `RunDetail`을 추가로 조회해야 한다. 스케줄은 향후 반복용이라 분석
  시점 설정을 그대로 따라가야 할 강한 이유가 없어 YAGNI.
- 클릭 즉시 기본값으로 스케줄을 만들어버리는 "one-click create" 방식.
  cron은 사용자가 신중히 정해야 하는 값이라 별도 폼 진입이 안전하다.

## UX

### 데스크톱 테이블
히스토리 테이블 끝에 액션 컬럼을 추가하고, 각 행에 작은 링크 형태의
`+ 트래킹` 버튼을 둔다. 행 클릭(상세 이동)과 동작이 충돌하지 않도록
`<Link>` 자체를 컬럼으로 두고, 체크박스와 동일한 패턴으로 분리한다.

```
| ☐ | Ticker | Date | Status | Decision | Conf | Created | + 트래킹 |
```

라벨은 한글 우선("트래킹"). 아이콘만 두지 않는 이유는 액션이 명시적으로
드러나는 편이 자동 분석이라는 의미와 잘 맞기 때문이다.

### 모바일 카드
카드 하단에 한 줄을 추가하고, 우측 정렬로 `+ 트래킹` 링크를 둔다.
상세 이동 Link(`<Link>` 카드 본문)와 겹치지 않도록 카드 본문 Link 바깥에
배치한다.

### 진입 후 화면
`/schedules/new` 진입 시:
- ScheduleForm의 ticker chip 목록에 query string의 ticker가 자동으로 추가
  되어 있다.
- 폼 상단에 한 줄짜리 breadcrumb: `"분석 #abc1234에서 시작 →"` 형태
  (`components/run/run-form.tsx`의 `from_sector` 패턴과 동일한 룩).
- 이후 사용자는 이름(name)과 cron만 정하면 된다. 다른 필드는 기본값 유지.

## 데이터 흐름

1. `HistoryTable` 각 행:
   `<Link href="/schedules/new?ticker=AAPL&from_run=<run_id>">+ 트래킹</Link>`
2. `/schedules/new` 페이지는 그대로. (서버 컴포넌트가 form을 mount)
3. `ScheduleForm`(`"use client"`):
   - `useSearchParams()`로 `ticker`, `from_run` 읽음.
   - `useState` 초기값으로 ticker chip을 prefill (자연스럽게 mount 시
     1회만 적용).
   - `from_run`이 있으면 breadcrumb 영역에 렌더링. run 상세 페이지로
     링크: `<Link href={"/history/" + from_run}>분석 #...</Link>`.

## 컴포넌트 책임

### `components/history/history-table.tsx`
- props/시그니처는 그대로.
- 테이블 헤더에 마지막 컬럼 추가 (`Actions`은 노출 라벨 대신 빈 헤더 또는
  `Track` 정도; 한글로 통일이 어려우면 빈 헤더 + sr-only 라벨).
- 각 행 마지막 셀에 `<Link>` 추가. `className`은 기존 hover/transition과
  분리해 명확한 액션처럼 보이도록 한다 (예: 작은 outline 배지).
- 모바일 카드 하단에 동일 링크 추가.

### `components/schedules/schedule-form.tsx`
- import에 `useSearchParams` 추가.
- 컴포넌트 초입에서 query 읽고, ticker chip 초기 상태를 prefill.
  ```ts
  const search = useSearchParams();
  const prefillTicker = search.get("ticker")?.toUpperCase() ?? "";
  const fromRun = search.get("from_run");
  const [tickers, setTickers] = useState<string[]>(
    prefillTicker ? [prefillTicker] : [],
  );
  ```
- form 상단(첫 섹션 위)에 `fromRun` 존재 시 breadcrumb 렌더.

## 에지 케이스

- **query에 ticker가 없는 경우**: 기존 동작과 동일. breadcrumb 미표시.
- **query ticker가 비유효 문자열**: 폼 제출 시점에 기존 validation
  (`tickers.length === 0`, 서버 응답 에러)으로 충분. 추가 검증 없음.
- **query ticker와 name 동기화**: 단일 ticker라 `name` placeholder
  ("Semi-cap weekly")는 그대로. name은 사용자가 직접 입력.
- **from_run에 해당하는 run이 삭제된 경우**: breadcrumb의 링크가 404가
  될 수 있으나 표시 자체는 무해. 별도 사전 검증 안 함.

## 테스트

E2E (Playwright):
- 히스토리 페이지에서 `+ 트래킹` 클릭 → `/schedules/new`로 이동, ticker
  chip이 prefill되어 있고 breadcrumb이 표시되는지 확인.
- name과 cron을 입력하고 제출 → `/schedules`로 이동, 새 스케줄이 목록에
  나타나는지 확인.

기존 unit/e2e 스위트(`history-table`, `schedule-form`)에 회귀가 없도록
한다.

## 변경 파일 요약

1. `web/components/history/history-table.tsx` — 액션 컬럼/링크 추가
   (데스크톱 + 모바일).
2. `web/components/schedules/schedule-form.tsx` — query prefill +
   breadcrumb.
3. `web/tests/e2e/history-to-schedule.spec.ts` (신규) — 위 흐름의 happy
   path E2E.
