// Playwright global setup — runs once before any test file.
//
// Why this exists:
//   On 2026-05-09 a Playwright/E2E setup ran `tradingagents-web set-password`
//   against the production DB (`~/.tradingagents/web.db`) and silently
//   overwrote the live login password. This guard refuses to start any test
//   run when WEB_DATABASE_URL is unset or resolves to the production DB.
//
// We intentionally do NOT auto-create the e2e DB here — that is the job of
// scripts/setup_e2e.sh, which the developer runs explicitly. This file only
// fails fast.

import * as os from "node:os";
import * as path from "node:path";

const PROD_DB_ABS = path.resolve(os.homedir(), ".tradingagents", "web.db");

function resolveSqlitePath(url: string | undefined): string | null {
  if (!url) return null;
  // sqlalchemy URL forms:
  //   sqlite:///rel/path   -> "rel/path"
  //   sqlite:////abs/path  -> "/abs/path"
  const m = url.match(/^sqlite:\/\/\/(\/?.*)$/);
  if (!m) return null;
  return path.resolve(m[1]);
}

export default async function globalSetup(): Promise<void> {
  const url = process.env.WEB_DATABASE_URL;
  const dbPath = resolveSqlitePath(url);

  if (!url) {
    throw new Error(
      [
        "[e2e/global-setup] WEB_DATABASE_URL is unset.",
        "Run `scripts/setup_e2e.sh` first, then start the backend with the",
        "test profile loaded:",
        "    set -a && source .env.test && set +a && \\",
        "      uv run uvicorn tradingagents_web.main:app --port 8000",
      ].join("\n"),
    );
  }

  if (dbPath && dbPath === PROD_DB_ABS) {
    throw new Error(
      [
        "[e2e/global-setup] REFUSING — WEB_DATABASE_URL points at the production DB.",
        `    resolved: ${dbPath}`,
        "    expected: a relative sqlite path inside the working tree.",
        "Use `.env.test` (committed at repo root) and `scripts/setup_e2e.sh`.",
      ].join("\n"),
    );
  }
}
