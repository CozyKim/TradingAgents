import type { Schedule } from "@/lib/schedules";

/** 관심종목 한 항목: 고유 ticker와 그 ticker에 연결된 스케줄 개수. */
export interface WatchlistItem {
  ticker: string;
  scheduleCount: number;
}

/**
 * 스케줄 목록에서 관심종목을 파생한다.
 *
 * 같은 ticker(대소문자 무시)는 한 항목으로 합치고 스케줄 개수를 센다.
 * source 구분 없이 user/holding 스케줄 모두 포함한다. ticker 알파벳순 정렬.
 */
export function deriveWatchlist(schedules: Schedule[]): WatchlistItem[] {
  const counts = new Map<string, number>();
  for (const s of schedules) {
    const ticker = s.ticker.toUpperCase();
    counts.set(ticker, (counts.get(ticker) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([ticker, scheduleCount]) => ({ ticker, scheduleCount }))
    .sort((a, b) => a.ticker.localeCompare(b.ticker));
}
