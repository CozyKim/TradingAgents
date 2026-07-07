import { describe, it, expect } from "vitest";
import { resolveMarket } from "../ticker-market";

describe("resolveMarket", () => {
  it("한국 거래소 티커(.KS/.KQ)를 KR로 판별한다", () => {
    expect(resolveMarket("005930.KS")?.market).toBe("KR");
    expect(resolveMarket("035720.KQ")?.market).toBe("KR");
  });

  it("소문자와 앞뒤 공백을 정규화한다", () => {
    expect(resolveMarket("005930.ks")?.market).toBe("KR");
    expect(resolveMarket("  AAPL  ")?.market).toBe("US");
  });

  it("접미사 없는 심볼과 미국 클래스주를 US로 판별한다", () => {
    expect(resolveMarket("AAPL")?.market).toBe("US");
    expect(resolveMarket("MSFT")?.market).toBe("US");
    expect(resolveMarket("BRK.B")?.market).toBe("US");
  });

  it("알려진 해외 거래소 접미사를 GLOBAL로 판별한다", () => {
    expect(resolveMarket("7203.T")?.market).toBe("GLOBAL");
    expect(resolveMarket("BMW.DE")?.market).toBe("GLOBAL");
    expect(resolveMarket("0700.HK")?.market).toBe("GLOBAL");
  });

  it("중남미 예탁증서(DR) 접미사를 GLOBAL로 판별한다", () => {
    expect(resolveMarket("NVDC34.SA")?.market).toBe("GLOBAL");
  });

  it("빈 문자열/공백이면 null을 반환한다", () => {
    expect(resolveMarket("")).toBeNull();
    expect(resolveMarket("   ")).toBeNull();
  });

  it("뱃지에 이모지와 접근성 라벨을 담는다", () => {
    const kr = resolveMarket("005930.KS");
    expect(kr?.emoji).toBe("🇰🇷");
    expect(kr?.aria).toBe("한국 상장");

    const us = resolveMarket("AAPL");
    expect(us?.emoji).toBe("🇺🇸");

    const global = resolveMarket("7203.T");
    expect(global?.emoji).toBe("🌐");
  });
});
