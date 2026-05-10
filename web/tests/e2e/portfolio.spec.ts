import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD ?? "test1234";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel(/비밀번호|password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /로그인|sign in/i }).click();
  // 로그인 후 루트("/") 또는 워크스페이스 하위 경로로 리다이렉트
  await page.waitForURL((url: URL) => url.pathname !== "/login", {
    timeout: 30_000,
  });
}

/**
 * 포트폴리오 상세 페이지로 이동.
 *
 * 1순위: /portfolio 목록의 첫 번째 holding 링크를 클릭.
 * 2순위(보유 종목이 시드되지 않은 환경): /portfolio/AAPL로 직접 이동.
 *   상세 페이지는 holding이 없어도 chart 카드 자체는 렌더한다.
 */
async function goToPortfolioDetail(page: Page) {
  await page.goto("/portfolio");
  await page.waitForLoadState("networkidle");
  // holdings-table.tsx의 ticker 링크는 `/portfolio/<TICKER>` 형태.
  const holdingLink = page
    .locator('a[href^="/portfolio/"]')
    .filter({ hasText: /^[A-Z0-9.\-]+$/ })
    .first();
  if (await holdingLink.count()) {
    await holdingLink.click();
  } else {
    await page.goto("/portfolio/AAPL");
  }
  // 인터벌 탭이 보일 때까지 대기 — chart가 렌더된 신호.
  await expect(
    page.getByRole("button", { name: "일", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
}

test.describe("portfolio detail chart", () => {
  test("renders candle chart and switches intervals", async ({ page }) => {
    await login(page);
    await goToPortfolioDetail(page);

    // 일/주/월 탭이 모두 클릭 가능하고 aria-pressed=true 로 토글된다.
    for (const label of ["주", "월", "일"]) {
      const tab = page.getByRole("button", { name: label, exact: true });
      await tab.click();
      await expect(tab).toHaveAttribute("aria-pressed", "true");
    }
  });

  test("indicator toolbar toggles persist across reload", async ({ page }) => {
    await login(page);
    await goToPortfolioDetail(page);

    // 초기 상태가 깨끗하도록 RSI가 켜져 있다면 한 번 더 눌러 끈다.
    const rsi = page.getByRole("button", { name: /^RSI$/ });
    if ((await rsi.getAttribute("aria-pressed")) === "true") {
      await rsi.click();
      await expect(rsi).toHaveAttribute("aria-pressed", "false");
    }

    // 보조지표 토글: RSI 켜기.
    await rsi.click();
    await expect(rsi).toHaveAttribute("aria-pressed", "true");

    await page.reload();
    // hydrate 후 다시 잡아야 함.
    const rsiAfter = page.getByRole("button", { name: /^RSI$/ });
    await expect(rsiAfter).toHaveAttribute("aria-pressed", "true", {
      timeout: 10_000,
    });

    // 정리: 다시 끄기.
    await rsiAfter.click();
    await expect(rsiAfter).toHaveAttribute("aria-pressed", "false");
  });
});
