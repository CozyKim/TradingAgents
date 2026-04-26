"use client";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { CompareColumn } from "@/components/history/compare-column";
import { cn } from "@/lib/utils";

export default function HistoryComparePage() {
  const sp = useSearchParams();
  const ids = (sp.get("ids") ?? "").split(",").filter(Boolean);
  const [active, setActive] = useState<0 | 1>(0);

  if (ids.length !== 2 || ids[0] === ids[1])
    return (
      <p className="px-4 md:px-6 py-6 text-xs text-signal-sell">
        Provide exactly two distinct run IDs: <code>?ids=a,b</code>.
      </p>
    );

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-2xl mx-auto">
      <h1 className="text-xl font-bold text-text-1 mb-3">Compare</h1>

      {/* Mobile: A/B tab switcher */}
      <div className="md:hidden flex gap-1 mb-3 text-xs">
        {[0, 1].map((i) => (
          <button
            key={i}
            type="button"
            onClick={() => setActive(i as 0 | 1)}
            className={cn(
              "flex-1 rounded-md px-2 py-1.5 border",
              active === i
                ? "border-accent text-text-1 bg-bg-2"
                : "border-border-1 text-text-3",
            )}
          >
            {i === 0 ? "A" : "B"}
          </button>
        ))}
      </div>

      <div className="md:hidden">
        <CompareColumn runId={ids[active]} />
      </div>

      <div className="hidden md:grid grid-cols-2 gap-4">
        <CompareColumn runId={ids[0]} />
        <CompareColumn runId={ids[1]} />
      </div>
    </div>
  );
}
