import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD ?? "test1234";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel(/비밀번호|password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /로그인|sign in/i }).click();
  await page.waitForURL((url: URL) => url.pathname !== "/login", {
    timeout: 30_000,
  });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
}

// 눈 토글 버튼(표시/숨기기). peek 버튼("잠깐 보기")과 이름이 겹치지 않는다.
const toggleButton = (page: Page) =>
  page.getByRole("button", { name: /자산 금액 (표시|숨기기)/ });

test.describe("dashboard hide balance", () => {
  test("접속 시 요약 금액이 기본 숨김이다", async ({ page }) => {
    await login(page);
    await expect(page.getByTestId("net-worth")).toHaveAttribute(
      "data-hidden",
      "true",
    );
    await expect(toggleButton(page)).toHaveAttribute("aria-pressed", "false");
  });

  test("눈 버튼으로 노출/숨김을 토글한다", async ({ page }) => {
    await login(page);

    await toggleButton(page).click();
    await expect(toggleButton(page)).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("net-worth")).toHaveAttribute(
      "data-hidden",
      "false",
    );

    await toggleButton(page).click();
    await expect(toggleButton(page)).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByTestId("net-worth")).toHaveAttribute(
      "data-hidden",
      "true",
    );
  });

  test("새로고침하면 다시 숨김으로 시작한다(저장 안 함)", async ({ page }) => {
    await login(page);

    await toggleButton(page).click();
    await expect(toggleButton(page)).toHaveAttribute("aria-pressed", "true");

    await page.reload();
    await page.waitForLoadState("networkidle");

    await expect(toggleButton(page)).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByTestId("net-worth")).toHaveAttribute(
      "data-hidden",
      "true",
    );
  });

  test("숫자를 탭하면 잠깐 보였다가 자동으로 다시 숨는다(peek)", async ({
    page,
  }) => {
    await login(page);

    const nw = page.getByTestId("net-worth");
    await expect(nw).toHaveAttribute("data-hidden", "true");
    await nw.click(); // peek 트리거
    await expect(page.getByTestId("net-worth")).toHaveAttribute(
      "data-hidden",
      "false",
    );

    // PEEK_MS(3000ms) + 여유 후 다시 숨김.
    await expect(page.getByTestId("net-worth")).toHaveAttribute(
      "data-hidden",
      "true",
      { timeout: 6000 },
    );
    // peek는 토글 상태를 바꾸지 않는다.
    await expect(toggleButton(page)).toHaveAttribute("aria-pressed", "false");
  });
});
