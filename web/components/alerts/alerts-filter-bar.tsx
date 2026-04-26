"use client";
import type { AlertType } from "@/lib/alerts";
import { cn } from "@/lib/utils";

const TYPES: { value: AlertType | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "signal_change", label: "Signal" },
  { value: "confidence_change", label: "Confidence" },
  { value: "run_completed", label: "Completed" },
  { value: "run_failed", label: "Run failed" },
  { value: "schedule_failed", label: "Schedule failed" },
];

export function AlertsFilterBar({
  type,
  unreadOnly,
  onChangeType,
  onToggleUnread,
}: {
  type: AlertType | "all";
  unreadOnly: boolean;
  onChangeType: (t: AlertType | "all") => void;
  onToggleUnread: (v: boolean) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap gap-1">
        {TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => onChangeType(t.value)}
            className={cn(
              "rounded-md px-2 py-1 text-xs border",
              type === t.value
                ? "bg-bg-2 border-border-2 text-text-1"
                : "bg-bg-1 border-border-1 text-text-2 hover:text-text-1",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <label className="ml-auto flex items-center gap-2 text-xs text-text-2">
        <input
          type="checkbox"
          checked={unreadOnly}
          onChange={(e) => onToggleUnread(e.target.checked)}
        />
        Unread only
      </label>
    </div>
  );
}
