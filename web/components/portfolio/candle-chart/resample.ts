import { startOfISOWeek, format, parseISO } from "date-fns";

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
