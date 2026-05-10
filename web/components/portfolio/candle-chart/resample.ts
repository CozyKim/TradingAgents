import { startOfISOWeek, format, parseISO } from "date-fns";
import type { PricePoint } from "@/lib/prices";

export type Interval = "1D" | "1W" | "1M";

/**
 * 일봉 날짜 문자열(YYYY-MM-DD)을 인터벌 bucket의 대표 날짜로 변환.
 *
 * - 1D: 항등
 * - 1W: 해당 ISO 주의 월요일
 * - 1M: 해당 월의 1일
 */
export function bucketKey(date: string, interval: Interval): string {
  if (interval === "1D") return date;
  if (interval === "1W") {
    const monday = startOfISOWeek(parseISO(date));
    return format(monday, "yyyy-MM-dd");
  }
  // "1M"
  return date.slice(0, 7) + "-01";
}

/**
 * 일봉 시리즈를 주봉 또는 월봉으로 압축. 시간순 정렬된 입력을 가정한다.
 */
export function resample(daily: PricePoint[], interval: Interval): PricePoint[] {
  if (interval === "1D") return daily;
  if (daily.length === 0) return [];

  type Acc = {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  };
  const buckets = new Map<string, Acc>();
  for (const p of daily) {
    const key = bucketKey(p.date, interval);
    const acc = buckets.get(key);
    if (!acc) {
      buckets.set(key, {
        date: key,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
        volume: p.volume,
      });
    } else {
      acc.high = Math.max(acc.high, p.high);
      acc.low = Math.min(acc.low, p.low);
      acc.close = p.close;
      acc.volume += p.volume;
    }
  }
  return [...buckets.values()];
}
