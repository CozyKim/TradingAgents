/**
 * E2E for the M6 sector analysis flow.
 *
 * Covers the full sector → ticker drilldown:
 *  1. /sectors page lists sectors (preset or freshly created).
 *  2. /sectors/new creates a user-defined sector and redirects to /sectors/<slug>.
 *  3. "리포트 새로 생성" kicks off a run (FakeSectorRunner) and the SSE
 *     progress page transitions through all 4 phases, then redirects back to
 *     the detail page with the new report visible.
 *  4. A candidate ticker card click lands on /run with the breadcrumb visible
 *     and the ticker prefilled.
 *  5. Preset DELETE attempts are rejected at the API layer (CSRF + 409).
 *
 * Requires WEB_FAKE_RUNNER=true on the backend so no Tavily / LLM calls happen.
 */
import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD ?? "test1234";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel(/비밀번호|password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /로그인|sign in/i }).click();
  await page.waitForURL((url: URL) => url.pathname !== "/login", {
    timeout: 30_000,
  });
}

test.describe("sector analysis end-to-end", () => {
  test("create sector → refresh report → candidate → /run prefill", async ({
    page,
  }) => {
    await login(page);

    // 1) /sectors list reachable
    await page.goto("/sectors");
    await expect(
      page.getByRole("heading", { name: /산업.*섹터/i }),
    ).toBeVisible();

    // 2) Create a user-defined sector via /sectors/new
    await page.getByRole("link", { name: /새 섹터/i }).click();
    await expect(page).toHaveURL(/\/sectors\/new/);
    const name = `e2e-sector-${Date.now()}`;
    await page.getByLabel(/이름/i).fill(name);
    await page.getByLabel(/키워드/i).fill("AI accelerator, GPU");
    await page.getByRole("button", { name: /^생성$/ }).click();
    // The form sets slug = slugify(name) — for ASCII the slug equals the lowercased name.
    await page.waitForURL(
      (url: URL) => url.pathname === `/sectors/${name.toLowerCase()}`,
      { timeout: 15_000 },
    );

    // 3) Trigger the first analysis run (FakeSectorRunner)
    await page
      .getByRole("button", { name: /리포트 새로 생성/i })
      .click();
    // Routed to /sectors/<slug>/runs/<rid>
    await page.waitForURL(/\/sectors\/.+\/runs\//, { timeout: 15_000 });
    await expect(
      page.getByRole("heading", { name: /분석 진행 중/i }),
    ).toBeVisible();

    // 4) After 4 phases the page redirects back to /sectors/<slug> with the
    //    new report visible. FakeSectorRunner takes < 1s.
    await page.waitForURL(
      (url: URL) => url.pathname === `/sectors/${name.toLowerCase()}`,
      { timeout: 20_000 },
    );
    await expect(page.getByText("가치사슬")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText("후보 종목")).toBeVisible();

    // 5) Click the first candidate-ticker "종목 분석" button → /run prefill
    const analyzeLink = page
      .getByRole("link", { name: /종목 분석/i })
      .first();
    await analyzeLink.click();
    await page.waitForURL(/\/run\?.*from_sector=/);
    // The breadcrumb mentions the source sector slug
    await expect(page.getByText("산업 리포트")).toBeVisible();
    // The ticker input is populated. The dummy candidate tickers from
    // FakeSectorRunner are NVDA + TSM; either should land in the input.
    const tickerInput = page.locator("#ticker");
    await expect(tickerInput).toHaveValue(/^(NVDA|TSM)$/);
  });

  test("preset sector DELETE is rejected (CSRF + 409 path)", async ({
    request,
  }) => {
    // Inject a preset row via direct API; require_xhr means we must send the
    // marker even for the DELETE that should 409 on the is_preset check —
    // otherwise we'd 403 first.
    const list = await request.get("/api/sectors");
    expect(list.status()).toBe(200);
    const sectors = (await list.json()) as Array<{
      id: number;
      is_preset: boolean;
    }>;
    const preset = sectors.find((s) => s.is_preset);
    test.skip(!preset, "No preset sector in test DB — fixture is metadata-only");
    if (!preset) return;
    const resp = await request.delete(`/api/sectors/${preset.id}`, {
      headers: { "X-Requested-With": "fetch" },
    });
    expect(resp.status()).toBe(409);
  });
});
