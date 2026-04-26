"use client";
import Link from "next/link";
import { Holding } from "@/lib/holdings";
import { RunListItem } from "@/lib/runs";
import { SignalBadge } from "@/components/shared/signal-badge";

export function PortfolioSignals({
  holdings,
  latestByTicker,
}: {
  holdings: Holding[];
  latestByTicker: Record<string, RunListItem | undefined>;
}) {
  if (holdings.length === 0)
    return (
      <p className="text-sm text-text-3">No holdings — add one in Portfolio.</p>
    );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-text-3 border-b border-border-1">
            <th className="text-left py-2">Ticker</th>
            <th>Latest decision</th>
            <th>Confidence</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const r = latestByTicker[h.ticker];
            return (
              <tr key={h.id} className="border-b border-border-1 hover:bg-bg-2">
                <td className="py-2 font-mono">
                  <Link className="hover:underline" href={`/portfolio/${h.ticker}`}>
                    {h.ticker}
                  </Link>
                </td>
                <td>
                  {r?.decision ? <SignalBadge decision={r.decision} /> : "—"}
                </td>
                <td className="font-mono tabular-nums">
                  {r?.confidence != null ? r.confidence.toFixed(2) : "—"}
                </td>
                <td className="text-xs text-text-3">
                  {r ? new Date(r.created_at).toLocaleString() : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
