"use client";
import Link from "next/link";

import { usePriceHistory } from "@/hooks/use-price-history";
import { useCurrency, formatPrice, currencyForTicker } from "@/lib/currency";
import type { WatchlistItem } from "@/lib/watchlist";
import { TickerLabel } from "@/components/ui/ticker-label";

/** 직전 종가 대비 등락%를 계산한다. 데이터가 부족하면 null. */
function changePct(points: { close: number }[], last: number | null): number | null {
  if (last == null || points.length < 2) return null;
  const prev = points[points.length - 2].close;
  if (!prev) return null;
  return ((last - prev) / prev) * 100;
}

export function WatchlistRow({ item, name }: { item: WatchlistItem; name?: string }) {
  const { ticker, scheduleCount } = item;
  // days=5: 현재가 + 직전 종가 등락 계산에 충분한 경량 호출. React Query 캐시 공유.
  const { data, isLoading, isError } = usePriceHistory(ticker, 5);
  const ctx = useCurrency();
  const cur = currencyForTicker(ticker);

  const last = data?.last_close ?? null;
  const pct = data ? changePct(data.points, last) : null;

  return (
    <tr className="border-b border-border-1 hover:bg-bg-2">
      <td className="py-2">
        <Link
          href={`/portfolio/${encodeURIComponent(ticker)}?from=watchlist`}
          className="text-sm text-accent hover:underline"
          data-testid="watchlist-link"
        >
          <TickerLabel ticker={ticker} name={name} />
        </Link>
      </td>
      <td className="text-right font-mono tabular-nums text-sm">
        {isLoading ? "…" : isError ? "—" : formatPrice(last, cur, ctx)}
      </td>
      <td
        className={`text-right font-mono tabular-nums text-sm ${
          pct == null ? "text-text-3" : pct >= 0 ? "text-pos" : "text-neg"
        }`}
      >
        {pct == null ? "—" : `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`}
      </td>
      <td className="text-right text-xs text-text-3">
        스케줄 {scheduleCount}개
      </td>
    </tr>
  );
}
