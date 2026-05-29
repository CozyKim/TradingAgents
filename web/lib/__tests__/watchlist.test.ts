import { describe, it, expect } from "vitest";
import { deriveWatchlist } from "../watchlist";
import type { Schedule } from "@/lib/schedules";

const mk = (id: number, ticker: string, source: "user" | "holding" = "user"): Schedule => ({
  id,
  name: `sched-${id}`,
  ticker,
  cron_expr: "30 9 * * *",
  timezone: "Asia/Seoul",
  preset: { analysts: [], debate_rounds: 1 },
  active: true,
  last_run: null,
  next_run: null,
  source,
  holding_id: null,
  created_at: "2026-05-30T00:00:00Z",
});

describe("deriveWatchlist", () => {
  it("returns empty array for no schedules", () => {
    expect(deriveWatchlist([])).toEqual([]);
  });

  it("dedupes the same ticker and counts schedules", () => {
    const out = deriveWatchlist([mk(1, "AAPL"), mk(2, "AAPL"), mk(3, "TSLA")]);
    expect(out).toEqual([
      { ticker: "AAPL", scheduleCount: 2 },
      { ticker: "TSLA", scheduleCount: 1 },
    ]);
  });

  it("sorts tickers alphabetically", () => {
    const out = deriveWatchlist([mk(1, "TSLA"), mk(2, "AAPL"), mk(3, "MSFT")]);
    expect(out.map((w) => w.ticker)).toEqual(["AAPL", "MSFT", "TSLA"]);
  });

  it("normalizes ticker case and treats them as the same symbol", () => {
    const out = deriveWatchlist([mk(1, "aapl"), mk(2, "AAPL")]);
    expect(out).toEqual([{ ticker: "AAPL", scheduleCount: 2 }]);
  });

  it("includes holding-sourced schedules too", () => {
    const out = deriveWatchlist([mk(1, "NVDA", "holding")]);
    expect(out).toEqual([{ ticker: "NVDA", scheduleCount: 1 }]);
  });
});
