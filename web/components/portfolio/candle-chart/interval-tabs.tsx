"use client";
import { cn } from "@/lib/utils";
import type { Interval } from "./resample";

const TABS: { key: Interval; label: string }[] = [
  { key: "1D", label: "일" },
  { key: "1W", label: "주" },
  { key: "1M", label: "월" },
];

export function IntervalTabs({
  value,
  onChange,
}: {
  value: Interval;
  onChange: (next: Interval) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-border-1 bg-bg-2/50 p-0.5 text-xs font-mono">
      {TABS.map((t) => (
        <button
          key={t.key}
          type="button"
          onClick={() => onChange(t.key)}
          className={cn(
            "px-3 py-1 rounded-sm transition-colors",
            value === t.key
              ? "bg-bg-1 text-text-1 shadow-sm"
              : "text-text-3 hover:text-text-2",
          )}
          aria-pressed={value === t.key}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
