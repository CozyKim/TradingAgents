import { describe, it, expect } from "vitest";
import { deriveRunState, STALL_MS } from "../run-liveness";

describe("deriveRunState", () => {
  it("returns running when a signal arrived within the stall window", () => {
    expect(
      deriveRunState({ lastSignalAt: 1000, now: 1000 + STALL_MS - 1, terminal: null }),
    ).toBe("running");
  });

  it("returns stalled when no signal for longer than the stall window", () => {
    expect(
      deriveRunState({ lastSignalAt: 1000, now: 1000 + STALL_MS + 1, terminal: null }),
    ).toBe("stalled");
  });

  it("prefers a terminal state over liveness", () => {
    expect(deriveRunState({ lastSignalAt: 0, now: 10 * STALL_MS, terminal: "completed" })).toBe("completed");
    expect(deriveRunState({ lastSignalAt: 0, now: 0, terminal: "cancelled" })).toBe("cancelled");
    expect(deriveRunState({ lastSignalAt: 0, now: 0, terminal: "failed" })).toBe("failed");
  });
});
