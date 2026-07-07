import { describe, expect, it } from "vitest";

import { MASK, maskMoney } from "@/lib/hide-balance";

describe("maskMoney", () => {
  it("숨김이면 MASK를 반환한다", () => {
    expect(maskMoney(true, "₩1,234,000")).toBe(MASK);
  });

  it("숨김이 아니면 포맷된 문자열을 그대로 반환한다", () => {
    expect(maskMoney(false, "₩1,234,000")).toBe("₩1,234,000");
  });

  it("숨김이면 값이 '—'여도 MASK를 반환한다", () => {
    expect(maskMoney(true, "—")).toBe(MASK);
  });
});
