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
