import { expect, test, type Page } from "@playwright/test";

const PASSWORD = process.env.E2E_PASSWORD ?? "test1234";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel(/비밀번호|password/i).fill(PASSWORD);
  await page.getByRole("button", { name: /로그인|sign in/i }).click();
  // 로그인 후 루트("/") 또는 워크스페이스 하위 경로로 리다이렉트
  await page.waitForURL((url: URL) => url.pathname !== "/login", { timeout: 30_000 });
}

test.describe("analysis chat", () => {
  test("completed 분석에서 채팅 시작 → 응답 확인 → 새로고침 후 영속", async ({ page }) => {
    await login(page);
    await page.goto("/history");
    await page.waitForLoadState("networkidle");
    // history-table.tsx에서 ticker 텍스트(`AAPL`)가 detail 링크
    const firstLink = page.getByRole("link", { name: /^[A-Z0-9.\-]+$/ }).first();
    await firstLink.click();

    // 채팅 섹션이 보일 때까지 대기 (completed 분석)
    await expect(page.getByText("이 분석에 대해 묻기")).toBeVisible({ timeout: 30_000 });

    await page.locator("textarea").fill("가격 흐름 다시 정리해줘");
    const submit = page.getByRole("button", { name: "보내기" });
    await expect(submit).toBeEnabled();
    await submit.click();

    // 사용자 메시지 즉시 표시
    await expect(page.getByText("가격 흐름 다시 정리해줘")).toBeVisible();
    // 어시스턴트 응답 도달
    await expect(page.locator("text=🤖 어시스턴트")).toBeVisible({ timeout: 90_000 });

    // 새로고침 후 영속 확인
    await page.reload();
    await expect(page.getByText("가격 흐름 다시 정리해줘")).toBeVisible();
  });

  test("failed/cancelled 분석은 후속 대화 비활성", async ({ page, request }) => {
    await login(page);
    // 백엔드 API로 failed 분석 존재 여부 사전 조회
    const failedResp = await request.get("/api/runs?status=failed&page_size=1");
    const failedData = await failedResp.json();
    const cancelledResp = await request.get("/api/runs?status=cancelled&page_size=1");
    const cancelledData = await cancelledResp.json();
    const target =
      failedData.items?.[0] ?? cancelledData.items?.[0] ?? null;
    if (!target) {
      test.skip(true, "no failed/cancelled analyses available in this environment");
      return;
    }
    await page.goto(`/history/${target.run_id}`);
    await expect(
      page.getByText("이 분석은 완료되지 않아 후속 대화를 할 수 없어요.")
    ).toBeVisible({ timeout: 10_000 });
  });
});
