"use client";
import Link from "next/link";
import { Activity } from "lucide-react";

import { useRunList } from "@/hooks/use-runs";
import { cn } from "@/lib/utils";

interface RunningRunsIndicatorProps {
  compact?: boolean;
}

export function RunningRunsIndicator({ compact = false }: RunningRunsIndicatorProps) {
  const { data } = useRunList(
    { status: "running", page_size: 5 },
    { refetchInterval: 5000, staleTime: 0 },
  );
  const items = data?.items ?? [];
  const first = items[0];
  if (!first) return null;

  const label =
    data && data.total > 1
      ? `${data.total} running`
      : `${first.ticker} running`;

  return (
    <Link
      href={`/run/${first.run_id}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-border-1 bg-bg-1 text-text-2 hover:bg-bg-2 hover:text-text-1",
        compact ? "px-2 py-1 text-2xs" : "px-2.5 py-1.5 text-xs",
      )}
    >
      <Activity className="h-3.5 w-3.5 text-accent" aria-hidden />
      <span>{label}</span>
    </Link>
  );
}
