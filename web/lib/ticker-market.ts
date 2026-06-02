export type Market = "US" | "KR" | "GLOBAL";

export interface MarketBadge {
  market: Market;
  emoji: string;
  /** 짧은 텍스트 라벨 (필요 시 사용): "KR" / "US" / "글로벌" */
  label: string;
  /** 접근성/툴팁 문구: "한국 상장" / "미국 상장" / "해외 상장" */
  aria: string;
}

// 야후 파이낸스 스타일 비(非)미국 거래소 접미사.
// 미국 보통주는 거래소 접미사가 없다는 점을 이용해, 한국도 아니고 이 목록에도
// 없으면 미국으로 본다. (BRK.B 같은 클래스주는 여기에 없으므로 자연히 US로 분류)
const GLOBAL_SUFFIXES = [
  ".T", ".HK", ".L", ".DE", ".PA", ".SS", ".SZ", ".TO", ".AX",
  ".SW", ".MI", ".HE", ".ST", ".AS", ".BR", ".MC", ".SI", ".TW",
  ".NS", ".BO", ".F", ".VI", ".LS", ".OL", ".CO", ".KL", ".JK",
];

const BADGES: Record<Market, MarketBadge> = {
  KR: { market: "KR", emoji: "🇰🇷", label: "KR", aria: "한국 상장" },
  US: { market: "US", emoji: "🇺🇸", label: "US", aria: "미국 상장" },
  GLOBAL: { market: "GLOBAL", emoji: "🌐", label: "글로벌", aria: "해외 상장" },
};

/**
 * 티커 문자열로 상장 시장을 판별해 뱃지 정보를 반환한다.
 * 비어 있으면 null을 반환한다(뱃지를 붙이지 않음).
 */
export function resolveMarket(ticker: string): MarketBadge | null {
  const normalized = ticker.trim().toUpperCase();
  if (!normalized) return null;
  if (normalized.endsWith(".KS") || normalized.endsWith(".KQ")) {
    return BADGES.KR;
  }
  if (GLOBAL_SUFFIXES.some((suffix) => normalized.endsWith(suffix))) {
    return BADGES.GLOBAL;
  }
  return BADGES.US;
}
