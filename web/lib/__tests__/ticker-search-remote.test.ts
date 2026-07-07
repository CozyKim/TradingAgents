import { describe, it, expect, vi, beforeEach } from "vitest";

const apiMock = vi.fn();
vi.mock("@/lib/api", () => ({ api: (...args: unknown[]) => apiMock(...args) }));

import { searchTickersRemote } from "../ticker-search-remote";
import { mergeResults, hasHangul } from "../ticker-search";
import type { SearchResult } from "../ticker-search";

const seed = (ticker: string): SearchResult => ({
  ticker, name: ticker, matched: "ticker", matchedText: ticker, score: 1000,
});
const remote = (ticker: string, name: string): SearchResult => ({
  ticker, name, matched: "name", matchedText: name, score: 0,
});

beforeEach(() => apiMock.mockReset());

describe("hasHangul", () => {
  it("detects hangul", () => {
    expect(hasHangul("삼성전자")).toBe(true);
    expect(hasHangul("nvidia")).toBe(false);
  });
});

describe("searchTickersRemote", () => {
  it("maps backend rows to SearchResult and passes the signal", async () => {
    apiMock.mockResolvedValue({
      results: [{ ticker: "SBUX", name: "스타벅스", market: "US", exchange: "NASDAQ" }],
    });
    const ctrl = new AbortController();
    const out = await searchTickersRemote("스타벅스", ctrl.signal);
    expect(out).toEqual([
      { ticker: "SBUX", name: "스타벅스", matched: "name", matchedText: "스타벅스", score: 0 },
    ]);
    expect(apiMock).toHaveBeenCalledWith(
      "/api/tickers/search?q=%EC%8A%A4%ED%83%80%EB%B2%85%EC%8A%A4",
      { signal: ctrl.signal },
    );
  });

  it("returns [] for blank query without calling api", async () => {
    expect(await searchTickersRemote("   ")).toEqual([]);
    expect(apiMock).not.toHaveBeenCalled();
  });
});

describe("mergeResults", () => {
  it("keeps seed on top and dedupes by ticker (seed wins)", () => {
    const out = mergeResults([seed("AAPL")], [remote("AAPL", "Apple"), remote("COST", "코스트코")]);
    expect(out.map((r) => r.ticker)).toEqual(["AAPL", "COST"]);
    expect(out[0].matched).toBe("ticker"); // 시드 항목 유지
  });

  it("dedupes case-insensitively and respects the limit", () => {
    const out = mergeResults([seed("aapl")], [remote("AAPL", "Apple")], 10);
    expect(out.map((r) => r.ticker)).toEqual(["aapl"]);
  });
});
