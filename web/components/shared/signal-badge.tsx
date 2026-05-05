import { cn } from "@/lib/utils";
import type { Decision as RunDecision } from "@/lib/runs";

type Decision = RunDecision | null;

const STYLES: Record<RunDecision, string> = {
  BUY: "bg-signal-buy/10 text-signal-buy",
  OVERWEIGHT: "bg-signal-buy/10 text-signal-buy",
  HOLD: "bg-text-3/15 text-text-2",
  UNDERWEIGHT: "bg-signal-sell/10 text-signal-sell",
  SELL: "bg-signal-sell/10 text-signal-sell",
};

const LABELS: Record<RunDecision, string> = {
  BUY: "매수",
  OVERWEIGHT: "비중확대",
  HOLD: "보유",
  UNDERWEIGHT: "비중축소",
  SELL: "매도",
};

export function SignalBadge({
  decision,
  className,
}: {
  decision: Decision;
  className?: string;
}) {
  if (!decision) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-md bg-bg-2 px-2 py-0.5 text-[12px] font-semibold text-text-3",
          className,
        )}
      >
        —
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[12px] font-bold tracking-[-0.01em]",
        STYLES[decision],
        className,
      )}
    >
      {LABELS[decision]}
    </span>
  );
}
