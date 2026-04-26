import { MarkdownText, type TextRenderMode } from "@/components/analysis/markdown-text";
import { cn } from "@/lib/utils";

const ROLE_STYLES: Record<string, string> = {
  market: "border-l-accent",
  social: "border-l-accent",
  news: "border-l-accent",
  fundamentals: "border-l-accent",
  research: "border-l-signal-buy",
  trader: "border-l-signal-hold",
  risk: "border-l-signal-sell",
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
  return (
    <div
      className={cn(
        "border border-border-1 border-l-2 bg-bg-1 rounded-md px-3 py-2",
        ROLE_STYLES[role] ?? "border-l-text-3",
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-2xs uppercase tracking-widest text-text-3 font-medium">
          {role}
        </span>
        {ts && <span className="text-2xs font-num text-text-3">{ts}</span>}
      </div>
      {renderMode === "plain" ? (
        <MarkdownText
          className="text-xs text-text-2 leading-snug"
          mode="plain"
          text={text}
        />
      ) : (
        <MarkdownText
          className="text-xs text-text-2 leading-snug [&_p]:leading-snug"
          text={text}
        />
      )}
    </div>
  );
}
