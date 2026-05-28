"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  mermaid: string;
}

export function ValueChainDiagram({ mermaid }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mermaid.trim()) return;
    let cancelled = false;

    (async () => {
      try {
        const m = (await import("mermaid")).default;
        // strict: don't allow arbitrary inline scripts in the diagram source.
        m.initialize({
          startOnLoad: false,
          theme: "neutral",
          securityLevel: "strict",
        });
        // Unique id so two diagrams on the same page don't collide.
        const id = `vc-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
        const { svg } = await m.render(id, mermaid);
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg;
        }
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "mermaid render failed";
          setError(msg);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [mermaid]);

  if (!mermaid.trim()) {
    return <p className="text-sm text-text-3">가치사슬 다이어그램 없음</p>;
  }
  if (error) {
    return (
      <div className="rounded-lg border border-signal-buy/40 bg-signal-buy/5 p-3 text-sm text-signal-buy">
        <p className="font-medium">다이어그램 렌더 실패</p>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs">
          {mermaid}
        </pre>
      </div>
    );
  }
  return <div ref={ref} className="w-full overflow-x-auto" />;
}
