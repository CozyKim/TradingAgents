"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useHoldings } from "@/hooks/use-holdings";
import { HoldingForm } from "@/components/portfolio/holding-form";
import { HoldingsTable } from "@/components/portfolio/holdings-table";
import { getPriceHistory } from "@/lib/prices";

export default function PortfolioPage() {
  const { data, isLoading, error } = useHoldings();
  const [prices, setPrices] = useState<Record<string, number | null>>({});

  useEffect(() => {
    if (!data?.items) return;
    let cancelled = false;
    (async () => {
      const result: Record<string, number | null> = {};
      await Promise.all(
        data.items.map(async (h) => {
          try {
            const r = await getPriceHistory(h.ticker, 5);
            result[h.ticker] = r.last_close;
          } catch {
            result[h.ticker] = null;
          }
        }),
      );
      if (!cancelled) setPrices(result);
    })();
    return () => {
      cancelled = true;
    };
  }, [data?.items]);

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <h1 className="text-xl font-bold text-text-1 mb-1">Portfolio</h1>
      <p className="text-xs text-text-3 mb-6">
        Track holdings and toggle daily auto-monitoring.
      </p>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Add holding</CardTitle>
        </CardHeader>
        <CardContent>
          <HoldingForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Holdings</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-text-3">Loading…</p>
          ) : error ? (
            <p className="text-sm text-neg">{(error as Error).message}</p>
          ) : (
            <HoldingsTable rows={data?.items ?? []} prices={prices} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
