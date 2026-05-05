import { MarkdownText, type TextRenderMode } from "@/components/analysis/markdown-text";
import { cn } from "@/lib/utils";

const ROLE_STYLES: Record<string, { ring: string; chip: string }> = {
  market: {
    ring: "ring-accent/30",
    chip: "bg-accent-muted text-accent",
  },
  social: {
    ring: "ring-accent/30",
    chip: "bg-accent-muted text-accent",
  },
  news: {
    ring: "ring-accent/30",
    chip: "bg-accent-muted text-accent",
  },
  fundamentals: {
    ring: "ring-accent/30",
    chip: "bg-accent-muted text-accent",
  },
  research: {
    ring: "ring-signal-buy/25",
    chip: "bg-signal-buy/10 text-signal-buy",
  },
  trader: {
    ring: "ring-text-3/30",
    chip: "bg-text-3/15 text-text-2",
  },
  risk: {
    ring: "ring-signal-sell/25",
    chip: "bg-signal-sell/10 text-signal-sell",
  },
};

const ROLE_LABEL: Record<string, string> = {
  market: "시장",
  social: "소셜",
  news: "뉴스",
  fundamentals: "펀더멘털",
  research: "리서치",
  trader: "트레이더",
  risk: "리스크",
};

export function AgentCard({
  role,
  text,
  ts,
  renderMode = "markdown",
}: {
  role: string;
  text: string;
  ts?: string | number;
  renderMode?: TextRenderMode;
}) {
  const style = ROLE_STYLES[role] ?? {
    ring: "ring-text-3/20",
    chip: "bg-bg-2 text-text-3",
  };
  return (
    <div
      className={cn(
        "rounded-2xl bg-bg-1 px-4 py-3.5 shadow-card ring-1 ring-inset",
        style.ring,
      )}
    >
      <div className="mb-2 flex items-center justify-between">
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-[11.5px] font-bold tracking-[-0.01em]",
            style.chip,
          )}
        >
          {ROLE_LABEL[role] ?? role}
        </span>
        {ts && (
          <span className="font-num text-[11px] tracking-[-0.01em] text-text-3">
            {ts}
          </span>
        )}
      </div>
      {renderMode === "plain" ? (
        <MarkdownText
          className="text-[13.5px] leading-relaxed text-text-2"
          mode="plain"
          text={text}
        />
      ) : (
        <MarkdownText
          className="text-[13.5px] leading-relaxed text-text-2 [&_p]:leading-relaxed"
          text={text}
        />
      )}
    </div>
  );
}
