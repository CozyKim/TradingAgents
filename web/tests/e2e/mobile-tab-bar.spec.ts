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

    // href로 단언한다. Playwright의 name 옵션은 기본이 부분일치라
    // name: "알림" 은 배지가 켜진 더보기 링크("더보기 (미확인 알림 3개)")를 잡는다.
    await expect(nav.locator('a[href="/alerts"]')).toHaveCount(0);
  });

  test("관심종목 탭은 /watchlist 로 간다", async ({ page }) => {
    await login(page);
    const nav = page.getByRole("navigation", { name: "Primary" });
    await nav.getByRole("link", { name: "관심종목" }).click();
    await page.waitForURL("**/watchlist");
    await expect(page.getByRole("heading", { name: "관심종목" })).toBeVisible();
  });

  test("미확인 알림이 있으면 더보기 탭에 배지와 접근성 이름이 붙는다", async ({
    page,
  }) => {
    await page.route("**/api/alerts/unread-count", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: '{"unread":150}',
      }),
    );
    await login(page);
    const nav = page.getByRole("navigation", { name: "Primary" });

    // 배지는 aria-hidden이므로 접근성 이름은 aria-label 하나뿐이다.
    await expect(
      nav.getByRole("link", { name: "더보기 (미확인 알림 150개)", exact: true }),
    ).toBeVisible();
    // 화면에는 클램된 값만 보인다.
    await expect(nav.getByText("99+")).toBeVisible();
  });

  test("더보기에 관심종목과 알림이 모두 있고 알림은 /alerts 로 간다", async ({
    page,
  }) => {
    await login(page);
    const nav = page.getByRole("navigation", { name: "Primary" });
    await nav.getByRole("link", { name: /더보기/ }).click();
    await page.waitForURL("**/more");

    // 탭바에도 "관심종목" 링크가 있으므로 본문(main)으로 범위를 좁힌다.
    const body = page.locator("main");
    await expect(body.getByRole("link", { name: "관심종목" })).toBeVisible();

    // Playwright의 name 옵션은 기본이 부분일치다. href로 한 번 더 못박는다.
    // main 안에는 상단바 UnreadBell도 href="/alerts" 링크를 갖고 있으므로,
    // 더보기 목록(<ul>)으로 범위를 좁혀야 진짜로 새 항목이 추가됐는지 검증할 수 있다.
    const list = body.getByRole("list");
    await expect(list.locator('a[href="/alerts"]')).toHaveCount(1);
    await list.locator('a[href="/alerts"]').click();
    await page.waitForURL("**/alerts");
  });
});

test.describe("ticker search overlay", () => {
  test("검색 결과를 고르면 종목 상세로 가고 뒤로가기 한 번에 돌아온다", async ({
    page,
  }) => {
    await login(page);

    // 실제 Yahoo/Naver 호출을 끊는다. 검증 대상은 선택→내비게이션→뒤로가기이지
    // 외부 응답이 아니다.
    await page.route("**/api/tickers/search**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          results: [
            { ticker: "AAPL", name: "Apple Inc.", market: "US", exchange: "NASDAQ" },
          ],
        }),
      });
    });

    await page.goto("/portfolio");
    await page.getByRole("button", { name: "티커 검색" }).click();

    const dialog = page.getByRole("dialog", { name: "티커 검색" });
    await expect(dialog).toBeVisible();

    await dialog.getByRole("combobox").fill("애플");
    await dialog.getByRole("option", { name: /AAPL/ }).click();

    await page.waitForURL("**/portfolio/AAPL");

    // pushState 더미 엔트리를 router.replace 가 치환했으므로 back 한 번이면 된다.
    await page.goBack();
    await expect(page).toHaveURL(/\/portfolio$/);
  });

  test("Escape 로 닫히고 URL은 바뀌지 않는다", async ({ page }) => {
    await login(page);
    await page.goto("/portfolio");
    const before = page.url();

    await page.getByRole("button", { name: "티커 검색" }).click();
    const dialog = page.getByRole("dialog", { name: "티커 검색" });
    await expect(dialog).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    expect(page.url()).toBe(before);
  });
});
