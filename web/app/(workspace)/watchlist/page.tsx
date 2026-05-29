"use client";
import { useMemo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSchedules } from "@/hooks/use-schedules";
import { deriveWatchlist } from "@/lib/watchlist";
import { WatchlistTable } from "@/components/watchlist/watchlist-table";

export default function WatchlistPage() {
  const { data, isLoading, error } = useSchedules();
  const items = useMemo(
    () => deriveWatchlist(data?.items ?? []),
    [data?.items],
  );

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-1 mb-1">관심종목</h1>
        <p className="text-xs text-text-3">
          스케줄에 등록된 모든 종목을 모아 봅니다. 종목을 누르면 차트와 분석 기록을 볼 수 있습니다.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>추적 중인 종목</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-text-3">Loading…</p>
          ) : error ? (
            <p className="text-sm text-neg">{(error as Error).message}</p>
          ) : (
            <WatchlistTable items={items} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
