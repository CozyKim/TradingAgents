"use client";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
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
        <p className="text-[14px] text-text-2">
          아직 보유 종목이 없어요.
        </p>
        <Link
          href="/portfolio"
          className="inline-flex h-10 items-center gap-1 rounded-xl bg-accent-muted px-4 text-[13px] font-bold text-accent hover:bg-[#D6E7FD]"
        >
          + 첫 종목 추가하기
        </Link>
      </div>
    );
  return (
    <ul className="-mx-2 flex flex-col">
      {holdings.map((h) => {
        const r = latestByTicker[h.ticker];
        return (
          <li key={h.id}>
            <Link
              href={`/portfolio/${h.ticker}`}
              className="toss-press flex items-center gap-3 rounded-xl px-2 py-3 hover:bg-bg-2"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-bg-2 text-[12px] font-extrabold tracking-[-0.04em] text-text-1">
                {h.ticker.slice(0, 2)}
              </div>
              <div className="flex flex-1 flex-col">
                <div className="flex items-center gap-2">
                  <span className="text-[15px] font-bold tracking-[-0.02em] text-text-1">
                    {h.ticker}
                  </span>
                  {r?.decision && <SignalBadge decision={r.decision} />}
                </div>
                <div className="font-num text-[12.5px] text-text-3">
                  {r?.created_at ? formatKST(r.created_at) : "분석 기록 없음"}
                </div>
              </div>
              <div className="flex items-center gap-1">
                {r?.confidence != null && (
                  <span className="font-num text-[14px] font-bold tracking-[-0.02em] text-text-1">
                    {(r.confidence * 100).toFixed(0)}
                    <span className="text-[11px] font-semibold text-text-3">
                      %
                    </span>
                  </span>
                )}
                <ChevronRight
                  className="h-4 w-4 text-text-3"
                  aria-hidden
                  strokeWidth={2.4}
                />
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
