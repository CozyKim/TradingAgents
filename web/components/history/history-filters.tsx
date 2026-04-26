"use client";
import { Decision, RunStatus } from "@/lib/runs";

export interface FilterState {
  ticker?: string;
  status?: RunStatus;
  decision?: Decision;
}

const STATUSES: RunStatus[] = ["running", "completed", "failed", "cancelled"];
const DECISIONS: Decision[] = ["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"];

export function HistoryFilters({
  value,
  onChange,
}: {
  value: FilterState;
  onChange: (next: FilterState) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3 mb-4">
      <div>
        <div className="text-2xs uppercase tracking-widest text-text-3 mb-1">
          Ticker
        </div>
        <input
          value={value.ticker ?? ""}
          placeholder="AAPL"
          onChange={(e) =>
            onChange({ ...value, ticker: e.target.value.toUpperCase() || undefined })
          }
          className="bg-bg-1 border border-border-1 rounded-md px-2 py-1 font-num text-xs w-28 uppercase"
        />
      </div>
      <div>
        <div className="text-2xs uppercase tracking-widest text-text-3 mb-1">
          Status
        </div>
        <select
          value={value.status ?? ""}
          onChange={(e) =>
            onChange({ ...value, status: (e.target.value || undefined) as RunStatus | undefined })
          }
          className="bg-bg-1 border border-border-1 rounded-md px-2 py-1 text-xs"
        >
          <option value="">All</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
      <div>
        <div className="text-2xs uppercase tracking-widest text-text-3 mb-1">
          Decision
        </div>
        <select
          value={value.decision ?? ""}
          onChange={(e) =>
            onChange({
              ...value,
              decision: (e.target.value || undefined) as Decision | undefined,
            })
          }
          className="bg-bg-1 border border-border-1 rounded-md px-2 py-1 text-xs"
        >
          <option value="">All</option>
          {DECISIONS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
