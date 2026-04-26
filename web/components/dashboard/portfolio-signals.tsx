"use client";
import Link from "next/link";
import { Holding } from "@/lib/holdings";
import { RunListItem } from "@/lib/runs";
import { SignalBadge } from "@/components/shared/signal-badge";
import { formatKST } from "@/lib/datetime";

export function PortfolioSignals({
  holdings,
  latestByTicker,
}: {
  holdings: Holding[];
  latestByTicker: Record<string, RunListItem | undefined>;
}) {
  if (holdings.length === 0)
    return (
      <div className="flex flex-col items-start gap-3 py-2">
        <p className="text-sm text-text-2">
          You don&apos;t have any holdings yet.
        </p>
        <Link
          href="/portfolio"
          className="inline-flex items-center gap-1 rounded-md border border-border-1 bg-bg-2 px-3 py-1.5 text-xs text-text-1 hover:bg-bg-1 hover:border-border-2"
        >
          + Add your first holding
        </Link>
      </div>
    );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-2xs uppercase tracking-wider text-text-3 border-b border-border-1">
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
                  {formatKST(r?.created_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
