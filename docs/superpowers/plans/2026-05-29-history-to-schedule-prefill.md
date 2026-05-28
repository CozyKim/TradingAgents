# 히스토리 → 스케줄 빠른 추가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 히스토리 테이블 각 행에서 한 번의 클릭으로 해당 ticker가 prefill된 `/schedules/new` 화면으로 진입할 수 있게 한다.

**Architecture:** `HistoryTable`에 액션 컬럼/링크를 추가해 `/schedules/new?ticker=<TICKER>&from_run=<RUN_ID>`로 보낸다. `ScheduleForm`은 mount 시 query string을 읽어 ticker chip을 초기화하고, `from_run`이 있으면 분석 기록 breadcrumb을 한 줄 띄운다. Prefill 범위는 ticker만으로 한정한다.

**Tech Stack:** Next.js 14 (app router, `useSearchParams`), React Query, Playwright (E2E), 기존 `components/run/run-form.tsx` 의 `from_sector` 패턴을 그대로 본뜬다.

**Spec:** `docs/superpowers/specs/2026-05-29-history-to-schedule-prefill-design.md`

---

## File Structure

- **Modify** `web/components/schedules/schedule-form.tsx`
  - `useSearchParams`로 `ticker`, `from_run` 읽기
  - ticker chip 초기 상태를 query 값으로 prefill
  - `from_run`이 있을 때 form 상단에 한 줄 breadcrumb (`<Link href="/history/<id>">`)
- **Modify** `web/components/history/history-table.tsx`
  - 데스크톱 테이블 헤더/행에 액션 컬럼 추가, `+ 트래킹` 링크
  - 모바일 카드 하단에 동일 링크
- **Create** `web/tests/e2e/history-to-schedule.spec.ts`
  - 분석 1건 생성 → 히스토리에서 `+ 트래킹` 클릭 → ScheduleForm prefill 확인 → 스케줄 생성까지 happy path

E2E 실행은 기존 sectors/portfolio/chat과 같은 구조를 따른다 (`scripts/setup_e2e.sh`로 빌드된 백엔드, `WEB_FAKE_RUNNER=true`).

---

## Task 1: ScheduleForm — query prefill (단위 동작)

ScheduleForm이 query string의 `ticker`를 읽어 chip으로 prefill하고, `from_run`이 있으면 breadcrumb을 그리도록 만든다. UI 진입점은 다음 Task에서 추가하므로, 이 Task는 form 자체의 동작만 변경한다.

**Files:**
- Modify: `web/components/schedules/schedule-form.tsx`

- [ ] **Step 1: 변경 전 form 구조 다시 확인**

Run: `sed -n '1,50p' web/components/schedules/schedule-form.tsx`

확인할 것:
- `"use client";` 선언
- `useState`로 `tickers: string[]` 보유
- import에 아직 `useSearchParams`/`Link` 없음

- [ ] **Step 2: import 추가**

`web/components/schedules/schedule-form.tsx` 상단 import 블록을 다음과 같이 수정한다.

기존:
```tsx
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
```

수정 후:
```tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
```

- [ ] **Step 3: query 읽고 ticker chip을 prefill**

`ScheduleForm` 함수 본문 첫머리(기존 `const router = useRouter();` 바로 아래)에 다음을 추가한다.

```tsx
  const router = useRouter();
  // Bridge from /history: ?ticker=AAPL&from_run=<run_id> prefills the
  // ticker chip and shows a one-line breadcrumb back to the source run.
  const search = useSearchParams();
  const prefillTicker = (search.get("ticker") ?? "").toUpperCase();
  const fromRun = search.get("from_run");

  const [name, setName] = useState("");
  const [tickers, setTickers] = useState<string[]>(
    prefillTicker ? [prefillTicker] : [],
  );
```

(기존 `const [tickers, setTickers] = useState<string[]>([]);` 줄을 위 블록의 마지막 줄로 대체한다.)

- [ ] **Step 4: breadcrumb 렌더링**

`return (` 다음의 `<form ...>` 첫 번째 자식으로, `Name` 필드 바로 위에 다음 블록을 삽입한다.

```tsx
      {fromRun && (
        <div className="rounded-md border border-accent/30 bg-accent-muted px-3 py-2 text-xs text-text-1">
          분석{" "}
          <Link
            href={`/history/${fromRun}`}
            className="font-semibold text-accent hover:underline"
          >
            #{fromRun.slice(0, 8)}
          </Link>
          <span className="text-text-3">에서 시작</span>
        </div>
      )}
```

스타일은 `components/run/run-form.tsx`의 `fromSector` breadcrumb과 동일한 토큰을 사용한다.

- [ ] **Step 5: 타입체크**

Run: `cd web && npx tsc --noEmit`
Expected: error 0건. (특히 `useSearchParams`의 반환은 `ReadonlyURLSearchParams | null`이지만 Next 14 app-router의 client component에서는 non-null로 다루는 것이 표준 패턴 — `?? ""` 가드로 충분히 처리됨.)

- [ ] **Step 6: 커밋**

```bash
git add web/components/schedules/schedule-form.tsx
git commit -m "feat(schedule): prefill ticker + show 'from run' breadcrumb"
```

---

## Task 2: HistoryTable — `+ 트래킹` 액션 링크 추가

히스토리 테이블 데스크톱/모바일 두 뷰에 단일 클릭 진입점을 추가한다.

**Files:**
- Modify: `web/components/history/history-table.tsx`

- [ ] **Step 1: 데스크톱 테이블 헤더에 액션 컬럼 추가**

기존 `<thead>` 블록의 마지막 `<th>` 뒤에 빈 헤더 셀을 추가한다.

기존:
```tsx
            <th className="text-right py-2 px-3">Created</th>
          </tr>
        </thead>
```

수정 후:
```tsx
            <th className="text-right py-2 px-3">Created</th>
            <th className="text-right py-2 px-3 w-28">
              <span className="sr-only">트래킹</span>
            </th>
          </tr>
        </thead>
```

- [ ] **Step 2: 데스크톱 행 마지막 셀로 링크 추가**

`<tbody>` 안 `tr` 매핑에서 마지막 `<td>` 뒤에 새 셀을 추가한다.

기존:
```tsx
              <td className="py-2 px-3 text-right text-text-3 font-num">
                {formatKST(r.created_at)}
              </td>
            </tr>
```

수정 후:
```tsx
              <td className="py-2 px-3 text-right text-text-3 font-num">
                {formatKST(r.created_at)}
              </td>
              <td className="py-2 px-3 text-right">
                <Link
                  href={`/schedules/new?ticker=${encodeURIComponent(
                    r.ticker,
                  )}&from_run=${r.run_id}`}
                  data-testid="track-link"
                  className="inline-flex items-center gap-1 rounded-md border border-border-1 px-2 py-1 text-2xs text-text-2 hover:bg-bg-2"
                >
                  + 트래킹
                </Link>
              </td>
            </tr>
```

`Link`는 파일 상단 첫 import에 이미 있으므로 추가 import 불필요.

- [ ] **Step 3: 모바일 카드 하단에 동일 링크 추가**

`<ul className="grid md:hidden ...">` 안 `<li>` 의 마지막 `<Link>` (`detailHref`로 가는 카드 본문) 다음에, 카드 하단 액션 영역을 추가한다.

기존:
```tsx
            <Link
              href={detailHref(r)}
              className="block px-3 pt-1 pb-2 text-2xs text-text-3"
            >
              <div className="flex items-center justify-between">
                <span className="font-num">{r.analysis_date}</span>
                <span>{r.status}</span>
              </div>
            </Link>
          </li>
```

수정 후:
```tsx
            <Link
              href={detailHref(r)}
              className="block px-3 pt-1 pb-2 text-2xs text-text-3"
            >
              <div className="flex items-center justify-between">
                <span className="font-num">{r.analysis_date}</span>
                <span>{r.status}</span>
              </div>
            </Link>
            <div className="flex justify-end border-t border-border-1 px-3 py-2">
              <Link
                href={`/schedules/new?ticker=${encodeURIComponent(
                  r.ticker,
                )}&from_run=${r.run_id}`}
                data-testid="track-link"
                className="inline-flex items-center gap-1 rounded-md border border-border-1 px-2 py-1 text-2xs text-text-2 hover:bg-bg-2"
              >
                + 트래킹
              </Link>
            </div>
          </li>
```

- [ ] **Step 4: 타입체크**

Run: `cd web && npx tsc --noEmit`
Expected: error 0건.

- [ ] **Step 5: 커밋**

```bash
git add web/components/history/history-table.tsx
git commit -m "feat(history): add '+ 트래킹' action linking to /schedules/new prefill"
```

---

## Task 3: E2E — 히스토리에서 트래킹까지 happy path

기존 e2e 스타일(`sectors.spec.ts`)에 맞춰 새 spec 파일을 만들고, "분석 1건 만들기 → 히스토리 → `+ 트래킹` → 스케줄 생성"을 한 번에 검증한다.

**Files:**
- Create: `web/tests/e2e/history-to-schedule.spec.ts`

- [ ] **Step 1: 테스트 파일 작성**

다음 내용으로 `web/tests/e2e/history-to-schedule.spec.ts` 를 생성한다.

```ts
/**
 * E2E for the history → schedule prefill bridge.
 *
 *  1. Log in with the test password.
 *  2. Create a single analysis run via /run so /history has a row to act on.
 *  3. From /history, click the row's "+ 트래킹" link.
 *  4. Verify we land on /schedules/new with the ticker prefilled (chip
 *     visible) and the "분석 #..." breadcrumb shown.
 *  5. Fill in name + accept default cron, submit, and verify the new
 *     schedule appears on /schedules.
 *
 * Requires WEB_FAKE_RUNNER=true so the analysis completes instantly without
 * external LLM/Tavily calls.
 */
import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD ?? "test1234";
const TICKER = "AAPL";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel(/비밀번호|password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /로그인|sign in/i }).click();
  await page.waitForURL((url: URL) => url.pathname !== "/login", {
    timeout: 30_000,
  });
}

test.describe("history → schedule prefill", () => {
  test("track button prefills /schedules/new and creates schedule", async ({
    page,
  }) => {
    await login(page);

    // 1) Create one analysis run via /run so /history has data.
    await page.goto("/run");
    await page
      .getByLabel(/티커/i)
      .fill(TICKER);
    // Combobox: confirm the AAPL option to seed the ticker state.
    await page.keyboard.press("Enter");
    await page.getByRole("button", { name: /분석.*시작|create|start/i }).click();
    // Routed to /run/<run_id> once submitted.
    await page.waitForURL(/\/run\/[^/]+/, { timeout: 15_000 });

    // 2) Go to /history and click the track link on the first row.
    await page.goto("/history");
    const firstTrack = page.getByTestId("track-link").first();
    await expect(firstTrack).toBeVisible();
    await firstTrack.click();

    // 3) Should land on /schedules/new with ticker + from_run query.
    await page.waitForURL(/\/schedules\/new\?.*ticker=AAPL/);
    await expect(page.getByText(/에서 시작/)).toBeVisible();
    // The ticker chip is rendered with the uppercase symbol.
    await expect(page.locator("text=AAPL").first()).toBeVisible();

    // 4) Fill name and submit (cron defaults to "30 9 * * *" KST).
    const scheduleName = `e2e-track-${Date.now()}`;
    await page.getByLabel(/^name$/i).fill(scheduleName);
    await page.getByRole("button", { name: /create schedule/i }).click();

    // 5) Lands on /schedules and the new row is visible.
    await page.waitForURL(/\/schedules$/, { timeout: 15_000 });
    await expect(page.getByText(scheduleName)).toBeVisible();
  });
});
```

- [ ] **Step 2: e2e 실행**

Run (백엔드는 별도 터미널에서 `set -a && source .env.test && set +a && uv run uvicorn tradingagents_web.main:app --port 8000` 가 떠 있어야 함, 그리고 `WEB_FAKE_RUNNER=true`):

```bash
cd web && npx playwright test tests/e2e/history-to-schedule.spec.ts --reporter=list
```

Expected: 1 passed.

만약 실패하면:
- "+ 트래킹" 링크가 잡히지 않으면 → `data-testid="track-link"` 가 데스크톱/모바일 둘 다에 있는지 확인. CI viewport에 따라 둘 중 한쪽만 보일 수 있음.
- "name" 라벨이 매칭 안 되면 → ScheduleForm의 `<Label htmlFor="name">Name</Label>` 그대로 두는지 확인.
- ticker chip이 안 보이면 → Task 1의 `useState` 초기값 prefill이 실제로 적용됐는지 확인.

- [ ] **Step 3: 커밋**

```bash
git add web/tests/e2e/history-to-schedule.spec.ts
git commit -m "test(history): e2e for history-to-schedule prefill bridge"
```

---

## Self-Review (작성자 체크리스트, 실행자는 무시)

**Spec coverage**
- 데스크톱 테이블 행 액션 → Task 2 step 2 ✓
- 모바일 카드 액션 → Task 2 step 3 ✓
- ScheduleForm prefill (ticker만) → Task 1 step 3 ✓
- breadcrumb (`분석 #abc1234에서 시작`) → Task 1 step 4 ✓
- E2E happy path → Task 3 ✓
- 분석 시점 analysts/rounds 자동 복제하지 않음 → spec out-of-scope, plan에도 들어가지 않음 ✓

**Placeholder scan**: TBD/TODO 없음. 모든 코드 블록이 실제 내용 포함.

**Type consistency**: `from_run` (query key), `prefillTicker` / `fromRun` (변수명), `data-testid="track-link"` 가 Task 1·2·3 전반에서 일관.

**기타**: ScheduleForm은 `tickers` chip prefill 외에 cron/name/analysts/rounds 등 기존 기본값을 그대로 유지하므로, 기존 사용자 흐름(직접 `/schedules/new` 진입) 회귀 위험은 query 없을 때 `prefillTicker=""` → `tickers=[]` 로 떨어져 기존과 동일.
