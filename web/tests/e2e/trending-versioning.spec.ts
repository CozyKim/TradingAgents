/**
 * E2E for scan-result persistence and version selector on /sectors/new.
 *
 * Verifies the versioning feature:
 *  1. Run a scan → dummy sectors from FakeTrendingFinder appear.
 *  2. Navigate away and return to /sectors/new.
 *  3. The previous scan result is restored from the server (not just React state).
 *  4. The version selector (<select aria-label="스캔 버전 선택">) is visible.
 *
 * Requires WEB_FAKE_RUNNER=true on the backend (set in .env.test by default)
 * so no Tavily / LLM calls happen and results are deterministic.
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

test.describe("핫 섹터 추천 버저닝 end-to-end", () => {
  test("스캔 결과가 재진입 후에도 복원되고 버전 셀렉터가 보인다", async ({
    page,
  }) => {
    await login(page);

    // 1) /sectors/new 진입 후 스캔 실행
    await page.goto("/sectors/new");
    await expect(
      page.getByRole("button", { name: /핫 섹터 추천받기/ }),
    ).toBeVisible();

    await page.getByRole("button", { name: /핫 섹터 추천받기/ }).click();

    // 2) FakeTrendingFinder 더미 결과 "온디바이스 AI" 카드가 나타날 때까지 대기
    await expect(page.getByText("온디바이스 AI").first()).toBeVisible({
      timeout: 15_000,
    });

    // 3) 다른 화면으로 이동했다가 복귀 (React state가 완전히 초기화됨)
    await page.goto("/sectors");
    await page.goto("/sectors/new");

    // 4) 직전 스캔 결과가 서버 저장본에서 복원되어 보인다
    await expect(page.getByText("온디바이스 AI").first()).toBeVisible({
      timeout: 15_000,
    });

    // 5) 버전 셀렉터(<select aria-label="스캔 버전 선택">)가 존재한다
    await expect(
      page.getByRole("combobox", { name: "스캔 버전 선택" }),
    ).toBeVisible();
  });
});
