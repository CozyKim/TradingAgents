/**
 * E2E for the watchlist (스케줄 파생 관심종목).
 *
 *  1. Log in with the test password.
 *  2. Create one analysis run via /run, then track it into a schedule
 *     (so a ticker exists in /api/schedules).
 *  3. Visit /watchlist and confirm the ticker row is present.
 *  4. Click the ticker → land on /portfolio/<ticker>?from=watchlist.
 *  5. Confirm the back link reads "관심종목으로" and returns to /watchlist.
 *
 * Requires WEB_FAKE_RUNNER=true so the analysis completes instantly.
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

test.describe("watchlist", () => {
  test("scheduled ticker shows on /watchlist and links to detail", async ({
    page,
  }) => {
    await login(page);

    // 1) Create one analysis run so /history has a row to track.
    await page.goto("/run");
    // exact 매칭. /티커/i 부분일치는 상단바 "티커 검색" 버튼까지 잡아 strict 위반이 난다.
    await page.getByLabel("티커", { exact: true }).fill(TICKER);
    await page.keyboard.press("Enter");
    await page.getByRole("button", { name: /분석 실행하기/ }).click();
    await page.waitForURL(/\/run\/[^/]+/, { timeout: 15_000 });

    // 2) Track it into a schedule via the history bridge.
    await page.goto("/history");
    await page.getByTestId("track-link").first().click();
    await page.waitForURL(/\/schedules\/new\?.*ticker=AAPL/);
    const scheduleName = `e2e-watchlist-${Date.now()}`;
    await page.getByLabel(/^name$/i).fill(scheduleName);
    await page.getByRole("button", { name: /create schedule/i }).click();
    await page.waitForURL(/\/schedules$/, { timeout: 15_000 });

    // 3) /watchlist should now list the ticker.
    await page.goto("/watchlist");
    const link = page.getByTestId("watchlist-link").filter({ hasText: TICKER });
    await expect(link.first()).toBeVisible();

    // 티커 옆에 한글 종목명이 병기된다 (AAPL → 애플, 실제 Naver 해석).
    await expect(link.first()).toContainText("애플", {
      timeout: 15_000,
    });

    // 4) Click → portfolio detail with from=watchlist.
    await link.first().click();
    await page.waitForURL(/\/portfolio\/AAPL\?.*from=watchlist/);

    // 5) Back link reads "관심종목으로" and returns to /watchlist.
    const back = page.getByRole("link", { name: /관심종목으로/ });
    await expect(back).toBeVisible();
    await back.click();
    await page.waitForURL(/\/watchlist$/, { timeout: 15_000 });
  });
});
