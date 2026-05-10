import { startOfISOWeek, format, parseISO } from "date-fns";
import type { PricePoint } from "@/lib/prices";
import type { SignalMarker } from "@/components/portfolio/price-chart";

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

/**
 * 신호 마커의 date를 인터벌 bucket key로 리맵.
 *
 * 한 bucket에 신호가 여러 개면 입력 순서상 첫 번째(가장 최신)만 유지한다.
 * 이는 page.tsx에서 created_at DESC 정렬 + seenDates 정책과 일관된다.
 */
export function alignSignals(
  signals: SignalMarker[],
  interval: Interval,
): SignalMarker[] {
  if (interval === "1D") return signals;
  const seen = new Map<string, SignalMarker>();
  for (const s of signals) {
    const key = bucketKey(s.date, interval);
    if (seen.has(key)) continue;
    seen.set(key, { ...s, date: key });
  }
  return [...seen.values()];
}
