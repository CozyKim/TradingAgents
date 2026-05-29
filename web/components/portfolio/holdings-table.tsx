"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Holding } from "@/lib/holdings";
import { useDeleteHolding } from "@/hooks/use-holdings";
import { useCurrency, formatPrice } from "@/lib/currency";
import { MonitorToggle } from "./monitor-toggle";
import { PnLCell } from "./pnl-cell";
import { QtyCell, AvgCostCell } from "./qty-cell";

export function HoldingsTable({
  rows,
  prices,
}: {
  rows: Holding[];
  prices: Record<string, number | null>;
}) {
  const del = useDeleteHolding();
  const ctx = useCurrency();
  if (rows.length === 0) {
    return (
      <p className="text-sm text-text-3 py-8 text-center">
        No holdings yet — add a ticker above.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-2xs uppercase tracking-wider text-text-3 border-b border-border-1">
            <th className="text-left py-2">Ticker</th>
            <th className="text-right">Qty</th>
            <th className="text-right">Avg Cost</th>
            <th className="text-right">Last</th>
            <th className="text-right">P&amp;L</th>
            <th className="text-center">Monitor</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => {
            const last = prices[h.ticker] ?? null;
            return (
              <tr key={h.id} className="border-b border-border-1 hover:bg-bg-2">
                <td className="py-2 font-mono">
                  <Link className="hover:underline" href={`/portfolio/${h.ticker}`}>
                    {h.ticker}
                  </Link>
                </td>
                <td className="text-right">
                  <QtyCell holdingId={h.id} qty={h.qty} />
                </td>
                <td className="text-right">
                  <AvgCostCell holdingId={h.id} avgCost={h.avg_cost} />
                </td>
                <td className="text-right font-mono tabular-nums">
                  {formatPrice(last, ctx)}
                </td>
                <td className="text-right">
                  <PnLCell qty={h.qty} avgCost={h.avg_cost} lastPrice={last} />
                </td>
                <td className="text-center">
                  <MonitorToggle holdingId={h.id} enabled={h.monitor_enabled} />
                </td>
                <td className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={del.isPending}
                    onClick={() => del.mutate(h.id)}
                  >
                    Remove
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
