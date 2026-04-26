import { cn } from "@/lib/utils";
import type { Decision as RunDecision } from "@/lib/runs";

type Decision = RunDecision | null;

const STYLES: Record<RunDecision, string> = {
  BUY: "bg-signal-buy/15 text-signal-buy",
  OVERWEIGHT: "bg-signal-buy/15 text-signal-buy",
  HOLD: "bg-signal-hold/15 text-signal-hold",
  UNDERWEIGHT: "bg-signal-sell/15 text-signal-sell",
  SELL: "bg-signal-sell/15 text-signal-sell",
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
          "px-1.5 py-0.5 rounded text-2xs font-mono uppercase tracking-wider bg-bg-2 text-text-3",
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
        "px-1.5 py-0.5 rounded text-2xs font-mono uppercase tracking-wider",
        STYLES[decision],
        className,
      )}
    >
      {decision}
    </span>
  );
}
