"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import type { Alert } from "@/lib/alerts";
import { cn } from "@/lib/utils";
import { formatKST } from "@/lib/datetime";
import { SignalBadge } from "@/components/shared/signal-badge";
import type { Decision } from "@/lib/runs";

const TYPE_LABEL: Record<Alert["type"], string> = {
  signal_change: "Signal change",
  confidence_change: "Confidence shift",
  run_completed: "Run complete",
  run_failed: "Run failed",
  schedule_failed: "Schedule failed",
};

const TYPE_TONE: Record<Alert["type"], string> = {
  signal_change: "text-accent",
  confidence_change: "text-warn",
  run_completed: "text-text-2",
  run_failed: "text-neg",
  schedule_failed: "text-neg",
};

const VALID_DECISIONS = new Set<Decision>([
  "BUY",
  "OVERWEIGHT",
  "HOLD",
  "UNDERWEIGHT",
  "SELL",
]);

function asDecision(v: unknown): Decision | null {
  return typeof v === "string" && (VALID_DECISIONS as Set<string>).has(v)
    ? (v as Decision)
    : null;
}

export function AlertRow({
  alert,
  onMarkRead,
}: {
  alert: Alert;
  onMarkRead: (id: number) => void;
}) {
  const summary = renderSummary(alert);
  return (
    <li
      className={cn(
        "border border-border-1 bg-bg-1 rounded-md p-3 flex items-start gap-3",
        !alert.read && "border-l-2 border-l-accent",
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 text-2xs uppercase tracking-widest">
          <span className={cn(TYPE_TONE[alert.type])}>
            {TYPE_LABEL[alert.type]}
          </span>
          {alert.ticker && (
            <span className="font-mono text-text-2">{alert.ticker}</span>
          )}
          <span className="text-text-3">
            {formatKST(alert.created_at)}
          </span>
        </div>
        <div className="mt-1 text-sm text-text-1">{summary}</div>
        {alert.analysis_id && (
          <Link
            href={`/history/${alert.analysis_id}`}
            className="text-xs text-text-2 underline-offset-2 hover:underline mt-1 inline-block"
          >
            Open analysis →
          </Link>
        )}
      </div>
      {!alert.read && (
        <button
          onClick={() => onMarkRead(alert.id)}
          className="text-xs text-text-2 hover:text-text-1"
        >
          Mark read
        </button>
      )}
    </li>
  );
}

function renderSummary(alert: Alert): ReactNode {
  const p = alert.payload as Record<string, unknown>;
  if (alert.type === "signal_change") {
    const conf = typeof p.confidence === "number" ? p.confidence : 0;
    return (
      <span className="flex items-center gap-1">
        <SignalBadge decision={asDecision(p.prev)} />
        <span>→</span>
        <SignalBadge decision={asDecision(p.curr)} />
        <span className="text-text-3 ml-1">conf {conf.toFixed(2)}</span>
      </span>
    );
  }
  if (alert.type === "confidence_change") {
    const prev = Number(p.prev);
    const curr = Number(p.curr);
    const delta = Number(p.delta);
    return (
      <span className="font-mono text-text-2">
        {prev.toFixed(2)} → {curr.toFixed(2)} (Δ
        {delta >= 0 ? "+" : ""}
        {delta.toFixed(2)})
      </span>
    );
  }
  if (alert.type === "run_completed") {
    const conf = typeof p.confidence === "number" ? p.confidence : 0;
    return (
      <span>
        <SignalBadge decision={asDecision(p.decision)} />
        <span className="text-text-3 ml-2">conf {conf.toFixed(2)}</span>
      </span>
    );
  }
  if (alert.type === "run_failed" || alert.type === "schedule_failed") {
    const error = typeof p.error === "string" ? p.error : "unknown error";
    return <span className="text-neg">{error}</span>;
  }
  return null;
}
