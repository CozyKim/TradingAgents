/**
 * E2E for the "핫 섹터 추천받기" flow on /sectors/new.
 *
 * Covers the full recommend → prefill journey:
 *  1. /sectors/new has the "🔥 핫 섹터 추천받기" button.
 *  2. Clicking it triggers a scan; FakeTrendingFinder returns three dummy
 *     sectors ("온디바이스 AI", "원전 SMR", "우주 발사체").
 *  3. The results are rendered as <li> cards with "이 섹터로 만들기" buttons.
 *  4. Clicking the button on the "온디바이스 AI" card prefills the name input.
 *
 * Requires WEB_FAKE_RUNNER=true on the backend (set in .env.test by default)
 * so no Tavily / LLM calls happen and the result is deterministic.
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

test.describe("핫 섹터 추천 end-to-end", () => {
  test("핫 섹터 추천 → 카드 클릭 → 폼 프리필", async ({ page }) => {
    await login(page);

    // 1) /sectors/new 진입
    await page.goto("/sectors/new");
    await expect(
      page.getByRole("button", { name: /핫 섹터 추천받기/ }),
    ).toBeVisible();

    // 2) "🔥 핫 섹터 추천받기" 버튼 클릭 → FakeTrendingFinder 스캔 시작
    await page.getByRole("button", { name: /핫 섹터 추천받기/ }).click();

    // 3) FakeTrendingFinder 더미 결과 "온디바이스 AI" 카드가 나타날 때까지 대기
    const card = page.getByText("온디바이스 AI").first();
    await expect(card).toBeVisible({ timeout: 15_000 });

    // 4) 해당 listitem 안의 "이 섹터로 만들기" 버튼 클릭
    await page
      .getByRole("listitem")
      .filter({ hasText: "온디바이스 AI" })
      .getByRole("button", { name: "이 섹터로 만들기" })
      .click();

    // 5) 이름 input(placeholder "예) 양자 컴퓨팅")에 "온디바이스 AI"가 프리필됐는지 검증
    await expect(page.getByPlaceholder("예) 양자 컴퓨팅")).toHaveValue(
      "온디바이스 AI",
    );
  });
});
