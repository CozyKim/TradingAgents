import { cn } from "@/lib/utils";
import type { Decision as RunDecision } from "@/lib/runs";

type Decision = RunDecision | null;

const TONE: Record<RunDecision, { bg: string; fg: string; arrow: string }> = {
  BUY: {
    bg: "bg-signal-buy/10",
    fg: "text-signal-buy",
    arrow: "▲",
  },
  OVERWEIGHT: {
    bg: "bg-signal-buy/10",
    fg: "text-signal-buy",
    arrow: "▲",
  },
  HOLD: {
    bg: "bg-text-3/15",
    fg: "text-text-2",
    arrow: "●",
  },
  UNDERWEIGHT: {
    bg: "bg-signal-sell/10",
    fg: "text-signal-sell",
    arrow: "▼",
  },
  SELL: {
    bg: "bg-signal-sell/10",
    fg: "text-signal-sell",
    arrow: "▼",
  },
};

const LABEL: Record<RunDecision, string> = {
  BUY: "매수",
  OVERWEIGHT: "비중 확대",
  HOLD: "보유",
  UNDERWEIGHT: "비중 축소",
  SELL: "매도",
};

export function VerdictCard({
  decision,
  confidence,
  preliminary = false,
}: {
  decision: Decision;
  confidence: number | null;
  preliminary?: boolean;
}) {
  const tone = decision ? TONE[decision] : null;
  return (
    <div className="rounded-2xl bg-bg-1 px-5 py-5 shadow-card">
      <div className="flex items-center gap-2">
        <span className="text-[12.5px] font-semibold tracking-[-0.01em] text-text-3">
          {preliminary ? "예비 결정" : "최종 결정"}
        </span>
        {preliminary && (
          <span className="inline-flex items-center rounded-full bg-bg-2 px-2 py-0.5 text-[10.5px] font-bold text-text-3">
            preliminary
          </span>
        )}
      </div>
      <div className="mt-2 flex items-end justify-between gap-3">
        <div className="flex items-baseline gap-2">
          {tone ? (
            <>
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-[20px] font-extrabold tracking-[-0.03em]",
                  tone.bg,
                  tone.fg,
                )}
              >
                <span className="text-[14px]">{tone.arrow}</span>
                {LABEL[decision!]}
              </span>
            </>
          ) : (
            <span className="inline-flex items-center rounded-xl bg-bg-2 px-3 py-1.5 text-[18px] font-extrabold text-text-3">
              —
            </span>
          )}
        </div>
        {confidence !== null && (
          <div className="flex flex-col items-end">
            <span className="text-[11px] font-semibold text-text-3">신뢰도</span>
            <span className="font-num text-[22px] font-extrabold tracking-[-0.03em] text-text-1">
              {(confidence * 100).toFixed(0)}
              <span className="text-[14px] font-bold text-text-3">%</span>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
