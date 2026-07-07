import { describe, expect, it } from "vitest";

import { balanceBlurClass } from "@/lib/hide-balance";

describe("balanceBlurClass", () => {
  it("숨김이면 강한 blur·scale·select-none 클래스를 포함한다", () => {
    const c = balanceBlurClass(true);
    expect(c).toContain("blur-[12px]");
    expect(c).toContain("select-none");
    expect(c).toContain("scale-[0.97]");
  });

  it("노출이면 blur 클래스를 포함하지 않는다", () => {
    expect(balanceBlurClass(false)).not.toContain("blur-[12px]");
  });

  it("숨김/노출 모두 filter·transform 전환 클래스를 포함한다", () => {
    expect(balanceBlurClass(true)).toContain("transition-[filter,transform]");
    expect(balanceBlurClass(false)).toContain("transition-[filter,transform]");
  });
});
