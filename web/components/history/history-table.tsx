"use client";
import Link from "next/link";

import { SignalBadge } from "@/components/shared/signal-badge";
import { RunListItem } from "@/lib/runs";

function fmt(ts: string) {
  return new Date(ts).toLocaleString(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function HistoryTable({ rows }: { rows: RunListItem[] }) {
  if (rows.length === 0) {
    return (
      <div className="border border-border-1 rounded-md py-12 text-center text-text-3 text-xs">
        No analyses yet.
      </div>
    );
  }
  return (
    <>
      <table className="hidden md:table w-full text-xs border-collapse">
        <thead className="text-text-3 uppercase tracking-widest text-[10px]">
          <tr className="border-b border-border-1">
            <th className="text-left py-2 px-3">Ticker</th>
            <th className="text-left py-2 px-3">Date</th>
            <th className="text-left py-2 px-3">Status</th>
            <th className="text-left py-2 px-3">Decision</th>
            <th className="text-right py-2 px-3">Confidence</th>
            <th className="text-right py-2 px-3">Created</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.run_id}
              className="border-b border-border-1 hover:bg-bg-2 transition-colors"
            >
              <td className="py-2 px-3">
                <Link href={`/history/${r.run_id}`} className="font-num font-bold">
                  {r.ticker}
                </Link>
              </td>
              <td className="py-2 px-3 font-num">{r.analysis_date}</td>
              <td className="py-2 px-3 text-text-2">{r.status}</td>
              <td className="py-2 px-3">
                <SignalBadge decision={r.decision} />
              </td>
              <td className="py-2 px-3 text-right font-num">
                {r.confidence !== null ? `${(r.confidence * 100).toFixed(0)}%` : "—"}
              </td>
              <td className="py-2 px-3 text-right text-text-3 font-num">
                {fmt(r.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="grid md:hidden gap-2">
        {rows.map((r) => (
          <li key={r.run_id}>
            <Link
              href={`/history/${r.run_id}`}
              className="block border border-border-1 rounded-md bg-bg-1 px-3 py-2"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-num font-bold">{r.ticker}</span>
                <SignalBadge decision={r.decision} />
              </div>
              <div className="flex items-center justify-between text-[10px] text-text-3">
                <span className="font-num">{r.analysis_date}</span>
                <span>{r.status}</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
