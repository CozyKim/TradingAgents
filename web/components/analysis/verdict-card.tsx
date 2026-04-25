import { SignalBadge } from "@/components/shared/signal-badge";
import type { Decision as RunDecision } from "@/lib/runs";

type Decision = RunDecision | null;

export function VerdictCard({
  decision,
  confidence,
  preliminary = false,
}: {
  decision: Decision;
  confidence: number | null;
  preliminary?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border-1 bg-gradient-to-br from-bg-1 to-bg-2 px-5 py-4">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] uppercase tracking-widest text-text-3">
          {preliminary ? "Preliminary" : "Verdict"}
        </span>
      </div>
      <div className="flex items-baseline gap-3">
        <SignalBadge decision={decision} className="text-lg px-3 py-1" />
        {confidence !== null && (
          <span className="text-sm font-num text-text-2">
            confidence {(confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
    </div>
  );
}
