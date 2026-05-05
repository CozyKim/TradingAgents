export function ProgressGauge({ step, total }: { step: number; total: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((step / total) * 100)) : 0;
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[12px] font-semibold tracking-[-0.01em] text-text-3">
          진행률
        </span>
        <span className="font-num text-[12.5px] font-bold tracking-[-0.01em] text-text-1">
          {step}/{total || "?"}
          <span className="ml-1 text-text-3">· {pct}%</span>
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-bg-0">
        <div
          className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
