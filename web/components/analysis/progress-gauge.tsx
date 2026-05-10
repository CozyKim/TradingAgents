const PHASES: ReadonlyArray<{ key: string; label: string }> = [
  { key: "analyst", label: "애널리스트" },
  { key: "research", label: "리서치" },
  { key: "trader", label: "트레이더" },
  { key: "risk", label: "리스크" },
];

export function ProgressGauge({
  step,
  total,
  phase,
  phaseLabel,
}: {
  step: number;
  total: number;
  phase?: string | null;
  phaseLabel?: string | null;
}) {
  const phaseTotal = total > 0 ? total : PHASES.length;
  const currentIndex = phase
    ? PHASES.findIndex((p) => p.key === phase)
    : Math.min(Math.max(step, 0), phaseTotal) - 1;
  const completed = Math.max(0, currentIndex + 1);
  const pct = Math.min(100, Math.round((completed / phaseTotal) * 100));
  const headerLabel =
    phaseLabel ?? (currentIndex >= 0 ? PHASES[currentIndex]?.label : null);

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[12px] font-semibold tracking-[-0.01em] text-text-3">
          진행 단계
        </span>
        <span className="font-num text-[12.5px] font-bold tracking-[-0.01em] text-text-1">
          {completed}/{phaseTotal}
          <span className="ml-1 text-text-3">
            {headerLabel ? `· ${headerLabel}` : `· ${pct}%`}
          </span>
        </span>
      </div>
      <ol className="grid grid-cols-4 gap-1.5">
        {PHASES.map((p, i) => {
          const state =
            i < completed ? "done" : i === completed ? "active" : "pending";
          return (
            <li
              key={p.key}
              className="flex flex-col items-stretch gap-1"
              aria-current={state === "active" ? "step" : undefined}
            >
              <div
                className={
                  "h-1.5 rounded-full transition-colors duration-500 " +
                  (state === "done"
                    ? "bg-accent"
                    : state === "active"
                      ? "bg-accent/60 animate-pulse"
                      : "bg-bg-0")
                }
              />
              <span
                className={
                  "text-center text-[11px] font-semibold tracking-[-0.01em] " +
                  (state === "pending" ? "text-text-3" : "text-text-1")
                }
              >
                {p.label}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
