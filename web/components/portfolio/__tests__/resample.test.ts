import { describe, it, expect } from "vitest";
import { bucketKey } from "../candle-chart/resample";

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
