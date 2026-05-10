import { describe, it, expect } from "vitest";
import { bucketKey, resample } from "../candle-chart/resample";
import type { PricePoint } from "@/lib/prices";

const mk = (d: string, o: number, h: number, l: number, c: number, v: number): PricePoint =>
  ({ date: d, open: o, high: h, low: l, close: c, volume: v });

describe("bucketKey", () => {
  it("1D returns the input date unchanged", () => {
    expect(bucketKey("2026-04-22", "1D")).toBe("2026-04-22");
  });

  it("1W returns the ISO Monday for any weekday", () => {
    // 2026-04-22 = Wednesday → Monday is 2026-04-20
    expect(bucketKey("2026-04-22", "1W")).toBe("2026-04-20");
    // 2026-04-20 (Monday) → itself
    expect(bucketKey("2026-04-20", "1W")).toBe("2026-04-20");
    // 2026-04-26 (Sunday, last day of ISO week) → 2026-04-20
    expect(bucketKey("2026-04-26", "1W")).toBe("2026-04-20");
    // 2026-04-27 (next Monday) → 2026-04-27
    expect(bucketKey("2026-04-27", "1W")).toBe("2026-04-27");
  });

  it("1M returns the first day of the month", () => {
    expect(bucketKey("2026-04-22", "1M")).toBe("2026-04-01");
    expect(bucketKey("2026-04-01", "1M")).toBe("2026-04-01");
    expect(bucketKey("2026-12-31", "1M")).toBe("2026-12-01");
  });
});

describe("resample", () => {
  it("1D returns input as-is", () => {
    const daily = [mk("2026-04-22", 1, 2, 0.5, 1.5, 10)];
    expect(resample(daily, "1D")).toEqual(daily);
  });

  it("returns empty for empty input", () => {
    expect(resample([], "1W")).toEqual([]);
    expect(resample([], "1M")).toEqual([]);
  });

  it("aggregates a full ISO week to one weekly bar", () => {
    // 2026-04-20 (Mon) ~ 2026-04-24 (Fri)
    const daily = [
      mk("2026-04-20", 100, 105, 99, 104, 1000),
      mk("2026-04-21", 104, 108, 103, 107, 1100),
      mk("2026-04-22", 107, 110, 106, 108, 1200),
      mk("2026-04-23", 108, 112, 107, 111, 1300),
      mk("2026-04-24", 111, 113, 109, 112, 1400),
    ];
    const out = resample(daily, "1W");
    expect(out).toHaveLength(1);
    expect(out[0]).toEqual({
      date: "2026-04-20",
      open: 100,
      high: 113,
      low: 99,
      close: 112,
      volume: 6000,
    });
  });

  it("splits across week boundaries", () => {
    const daily = [
      mk("2026-04-24", 100, 105, 99, 104, 1000),
      mk("2026-04-27", 104, 110, 103, 108, 2000),
    ];
    const out = resample(daily, "1W");
    expect(out.map((p) => p.date)).toEqual(["2026-04-20", "2026-04-27"]);
    expect(out[0].volume).toBe(1000);
    expect(out[1].volume).toBe(2000);
  });

  it("aggregates a month to one monthly bar", () => {
    const daily = [
      mk("2026-04-01", 100, 110, 99, 105, 100),
      mk("2026-04-15", 105, 115, 104, 112, 200),
      mk("2026-04-30", 112, 120, 111, 118, 300),
    ];
    const out = resample(daily, "1M");
    expect(out).toEqual([
      { date: "2026-04-01", open: 100, high: 120, low: 99, close: 118, volume: 600 },
    ]);
  });
});
