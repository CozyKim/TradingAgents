"use client";
import Link from "next/link";

import type { WatchlistItem } from "@/lib/watchlist";
import { WatchlistRow } from "./watchlist-row";

export function WatchlistTable({ items }: { items: WatchlistItem[] }) {
  if (items.length === 0)
    return (
      <div className="py-8 text-center text-sm text-text-3">
        <p>아직 추적 중인 종목이 없습니다.</p>
        <Link href="/schedules/new" className="text-accent hover:underline">
          스케줄 만들기 →
        </Link>
      </div>
    );

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-2xs uppercase tracking-wider text-text-3 border-b border-border-1">
            <th className="text-left py-2">Ticker</th>
            <th className="text-right">현재가</th>
            <th className="text-right">등락</th>
            <th className="text-right">스케줄</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <WatchlistRow key={item.ticker} item={item} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
