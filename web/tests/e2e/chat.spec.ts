import { expect, test } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD ?? "test1234";

async function login(page) {
  await page.goto("/login");
  await page.getByLabel(/비밀번호|password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /로그인|sign in/i }).click();
  // 로그인 후 루트("/") 또는 워크스페이스 하위 경로로 리다이렉트
  await page.waitForURL(url => url.pathname !== "/login", { timeout: 30_000 });
}

test.describe("analysis chat", () => {
  test("completed 분석에서 채팅 시작 → 응답 확인 → 새로고침 후 영속", async ({ page }) => {
    await login(page);
    await page.goto("/history");
    const firstLink = page.locator("a[href*='/history/']").first();
    await firstLink.click();

    // 채팅 섹션이 보일 때까지 대기 (completed 분석)
    await expect(page.getByText("이 분석에 대해 묻기")).toBeVisible({ timeout: 30_000 });

    await page.locator("textarea").fill("가격 흐름 다시 정리해줘");
    await page.getByRole("button", { name: "보내기" }).click();

    // 사용자 메시지 즉시 표시
    await expect(page.getByText("가격 흐름 다시 정리해줘")).toBeVisible();
    // 어시스턴트 응답 도달
    await expect(page.locator("text=🤖 어시스턴트")).toBeVisible({ timeout: 90_000 });

    // 새로고침 후 영속 확인
    await page.reload();
    await expect(page.getByText("가격 흐름 다시 정리해줘")).toBeVisible();
  });

  test("failed/cancelled 분석은 후속 대화 비활성", async ({ page }) => {
    await login(page);
    await page.goto("/history?status=failed");
    const failedLink = page.locator("a[href*='/history/']").first();
    if (!(await failedLink.count())) {
      test.skip(true, "no failed analyses available");
      return;
    }
    await failedLink.click();
    await expect(
      page.getByText("이 분석은 완료되지 않아 후속 대화를 할 수 없어요.")
    ).toBeVisible();
  });
});
