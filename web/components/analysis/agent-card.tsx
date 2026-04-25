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
}: {
  role: string;
  text: string;
  ts?: string | number;
}) {
  return (
    <div
      className={cn(
        "border border-border-1 border-l-2 bg-bg-1 rounded-md px-3 py-2",
        ROLE_STYLES[role] ?? "border-l-text-3",
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-widest text-text-3 font-medium">
          {role}
        </span>
        {ts && <span className="text-[10px] font-num text-text-3">{ts}</span>}
      </div>
      <pre className="text-xs text-text-2 whitespace-pre-wrap font-sans leading-snug">
        {text}
      </pre>
    </div>
  );
}
