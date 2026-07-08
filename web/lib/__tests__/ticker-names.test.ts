import { describe, it, expect, vi, beforeEach } from "vitest";

const apiMock = vi.fn();
vi.mock("@/lib/api", () => ({ api: (...args: unknown[]) => apiMock(...args) }));

import { fetchTickerNames, resolveDisplayName } from "../ticker-names";

beforeEach(() => apiMock.mockReset());

describe("fetchTickerNames", () => {
  it("uppercases, dedupes, and passes the signal", async () => {
    apiMock.mockResolvedValue({ names: { AAPL: "애플" } });
    const ctrl = new AbortController();

    const out = await fetchTickerNames(["aapl", "AAPL", " aapl "], ctrl.signal);

    expect(out).toEqual({ AAPL: "애플" });
    expect(apiMock).toHaveBeenCalledWith("/api/tickers/names?tickers=AAPL", {
      signal: ctrl.signal,
    });
  });

  it("encodes tickers containing special characters", async () => {
    apiMock.mockResolvedValue({ names: {} });
    await fetchTickerNames(["005930.KS", "BRK-B"]);
    expect(apiMock).toHaveBeenCalledWith(
      "/api/tickers/names?tickers=005930.KS%2CBRK-B",
      { signal: undefined },
    );
  });

  it("returns {} for an empty list without calling api", async () => {
    expect(await fetchTickerNames([])).toEqual({});
    expect(await fetchTickerNames(["  "])).toEqual({});
    expect(apiMock).not.toHaveBeenCalled();
  });
});

describe("resolveDisplayName", () => {
  it("looks up case-insensitively", () => {
    expect(resolveDisplayName({ AAPL: "애플" }, "aapl")).toBe("애플");
  });

  it("returns undefined for a missing key or absent map", () => {
    expect(resolveDisplayName({ AAPL: "애플" }, "NVDA")).toBeUndefined();
    expect(resolveDisplayName(undefined, "AAPL")).toBeUndefined();
  });
});
