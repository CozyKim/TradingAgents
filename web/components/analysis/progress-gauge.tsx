export function ProgressGauge({ step, total }: { step: number; total: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((step / total) * 100)) : 0;
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-2xs uppercase tracking-widest text-text-3">Progress</span>
        <span className="text-2xs font-num text-text-2">
          {step}/{total || "?"} · {pct}%
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-bg-2 overflow-hidden">
        <div
          className="h-full bg-accent transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
