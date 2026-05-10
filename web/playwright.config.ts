import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 120_000,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  // Fails fast if WEB_DATABASE_URL is missing or points at ~/.tradingagents/web.db.
  globalSetup: require.resolve("./tests/e2e/global-setup"),
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3030",
    headless: true,
    ignoreHTTPSErrors: true,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
