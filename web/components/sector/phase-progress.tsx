"use client";

import type { RunUiState } from "@/lib/run-liveness";

const PHASES: { key: string; label: string }[] = [
  { key: "macro", label: "거시 환경" },
  { key: "value_chain", label: "가치사슬" },
  { key: "competitive", label: "경쟁 구도" },
  { key: "outlook", label: "투자 전망" },
];

export function PhaseProgress({
  current,
  state,
}: {
  current: string | null;
  state?: RunUiState;
}) {
  const currentIdx = current
    ? PHASES.findIndex((p) => p.key === current)
    : -1;
  const stalled = state === "stalled";
  return (
    <ol className="flex items-center gap-2">
      {PHASES.map((p, i) => {
        const done = i < currentIdx;
        const active = i === currentIdx;
        return (
          <li key={p.key} className="flex flex-1 items-center gap-2">
            <div
              className={[
                "flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium",
                done
                  ? "bg-emerald-500 text-white"
                  : active
                    ? stalled
                      ? "bg-amber-500 text-white"
                      : "bg-accent text-white animate-pulse"
                    : "bg-bg-2 text-text-3",
              ].join(" ")}
            >
              {i + 1}
            </div>
            <span
              className={
                active
                  ? "text-text-1 font-medium"
                  : done
                    ? "text-text-2"
                    : "text-text-3"
              }
            >
              {p.label}
            </span>
            {i < PHASES.length - 1 && (
              <div
                className={`h-px flex-1 ${
                  done ? "bg-emerald-500" : "bg-bg-2"
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
