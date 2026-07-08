/**
 * E2E for the mobile bottom tab bar + top-bar ticker search.
 *
 * playwright.config.ts의 프로젝트는 Desktop Chrome 하나뿐이고 탭바는 md:hidden 이므로
 * 이 스펙만 모바일 뷰포트로 강제한다.
 */
import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD ?? "test1234";

test.use({ viewport: { width: 390, height: 844 } });

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel(/비밀번호|password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /로그인|sign in/i }).click();
  await page.waitForURL((url: URL) => url.pathname !== "/login", {
    timeout: 30_000,
  });
}

test.describe("mobile tab bar", () => {
  test("탭은 홈·포트폴리오·분석·관심종목·더보기이고 알림 탭은 없다", async ({
    page,
  }) => {
    await login(page);
    const nav = page.getByRole("navigation", { name: "Primary" });

    await expect(nav.getByRole("link", { name: "홈" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "포트폴리오" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "분석" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "관심종목" })).toBeVisible();
    await expect(nav.getByRole("link", { name: /더보기/ })).toBeVisible();

    await expect(nav.getByRole("link", { name: "알림" })).toHaveCount(0);
  });

  test("관심종목 탭은 /watchlist 로 간다", async ({ page }) => {
    await login(page);
    const nav = page.getByRole("navigation", { name: "Primary" });
    await nav.getByRole("link", { name: "관심종목" }).click();
    await page.waitForURL("**/watchlist");
    await expect(page.getByRole("heading", { name: "관심종목" })).toBeVisible();
  });
});
