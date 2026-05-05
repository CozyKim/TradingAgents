import { cn } from "@/lib/utils";

export function MetricCard({
  label,
  value,
  delta,
  tone = "neutral",
}: {
  label: string;
  value: string;
  delta?: string;
  tone?: "neutral" | "pos" | "neg";
}) {
  const toneCls =
    tone === "pos"
      ? "text-signal-buy"
      : tone === "neg"
        ? "text-signal-sell"
        : "text-text-1";
  return (
    <div className="rounded-2xl bg-bg-1 px-5 py-5 shadow-card">
      <div className="text-[13px] font-semibold tracking-[-0.01em] text-text-3">
        {label}
      </div>
      <div
        className={cn(
          "font-num mt-1 text-[26px] font-extrabold leading-tight tracking-[-0.03em]",
          toneCls,
        )}
      >
        {value}
      </div>
      {delta && (
        <div className="font-num mt-1 text-[12.5px] tracking-[-0.01em] text-text-3">
          {delta}
        </div>
      )}
    </div>
  );
}
