import { Card, CardContent } from "@/components/ui/card";
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
    tone === "pos" ? "text-pos" : tone === "neg" ? "text-neg" : "text-text-1";
  return (
    <Card>
      <CardContent className="py-4">
        <div className="text-2xs uppercase tracking-widest text-text-3">
          {label}
        </div>
        <div className={cn("font-mono text-xl tabular-nums mt-1", toneCls)}>
          {value}
        </div>
        {delta && (
          <div className="text-xs text-text-3 mt-1 font-mono">{delta}</div>
        )}
      </CardContent>
    </Card>
  );
}
