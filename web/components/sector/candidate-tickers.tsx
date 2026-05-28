"use client";

import Link from "next/link";

import type { CandidateTicker } from "@/lib/sectors";

interface Props {
  candidates: CandidateTicker[];
  fromSectorSlug: string;
  fromReportId: number;
}

export function CandidateTickers({
  candidates,
  fromSectorSlug,
  fromReportId,
}: Props) {
  if (candidates.length === 0) {
    return <p className="text-sm text-text-3">후보 종목 없음</p>;
  }
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {candidates.map((c) => (
        <div
          key={c.ticker}
          className="rounded-lg border border-border-1 bg-bg-1 p-4"
        >
          <div className="flex items-baseline justify-between gap-3">
            <div>
              <h4 className="font-semibold text-text-1">{c.name}</h4>
              <p className="text-xs text-text-3">
                {c.ticker} · {c.stage}
              </p>
            </div>
            <Link
              href={{
                pathname: "/run",
                query: {
                  ticker: c.ticker,
                  from_sector: fromSectorSlug,
                  from_report: fromReportId,
                },
              }}
              className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
            >
              종목 분석
            </Link>
          </div>
          <p className="mt-2 text-sm text-text-2">{c.reason}</p>
        </div>
      ))}
    </div>
  );
}
