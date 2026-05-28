"use client";

import { useMemo, useState } from "react";

import type { CompanyShare } from "@/lib/sectors";

const BASIS_LABEL: Record<CompanyShare["share_basis"], string> = {
  reported: "공시",
  estimated: "추정",
  unknown: "불명",
};

// Standard Tailwind palette colors — these are not project-specific tokens,
// they're built into Tailwind so they render correctly regardless of the
// project's custom color palette.
const BASIS_COLOR: Record<CompanyShare["share_basis"], string> = {
  reported: "bg-emerald-100 text-emerald-700",
  estimated: "bg-amber-100 text-amber-700",
  unknown: "bg-slate-100 text-slate-600",
};

export function CompaniesTable({ companies }: { companies: CompanyShare[] }) {
  const stages = useMemo(() => {
    const map = new Map<string, CompanyShare[]>();
    for (const c of companies) {
      const list = map.get(c.stage) ?? [];
      list.push(c);
      map.set(c.stage, list);
    }
    // Sort each stage's companies by share_value desc so the leader shows up first.
    for (const list of map.values()) {
      list.sort((a, b) => b.share_value - a.share_value);
    }
    return [...map.entries()];
  }, [companies]);

  if (companies.length === 0) {
    return <p className="text-sm text-text-3">기업 데이터 없음</p>;
  }

  return (
    <div className="space-y-6">
      {stages.map(([stage, list]) => (
        <section key={stage} data-stage={stage}>
          <h3 className="mb-2 text-sm font-semibold text-text-2">{stage}</h3>
          <div className="overflow-x-auto rounded-lg border border-border-1">
            <table className="min-w-full text-sm">
              <thead className="bg-bg-1 text-text-3">
                <tr>
                  <th className="px-3 py-2 text-left">기업</th>
                  <th className="px-3 py-2 text-right">점유율</th>
                  <th className="px-3 py-2 text-left">근거</th>
                  <th className="px-3 py-2 text-left">출처</th>
                </tr>
              </thead>
              <tbody>
                {list.map((c) => (
                  <CompanyRow key={`${c.stage}-${c.name}`} c={c} />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}

function CompanyRow({ c }: { c: CompanyShare }) {
  const [showSources, setShowSources] = useState(false);
  return (
    <tr className="border-t border-border-1">
      <td className="px-3 py-2">
        <span className="font-medium text-text-1">{c.name}</span>
        {c.ticker && <span className="ml-2 text-text-3">({c.ticker})</span>}
      </td>
      <td className="px-3 py-2 text-right font-mono">
        {c.share_value.toFixed(1)}%
      </td>
      <td className="px-3 py-2">
        <span className={`rounded px-2 py-0.5 text-xs ${BASIS_COLOR[c.share_basis]}`}>
          {BASIS_LABEL[c.share_basis]} · {c.confidence}
        </span>
      </td>
      <td className="px-3 py-2">
        {c.sources.length === 0 ? (
          <span className="text-text-3">—</span>
        ) : (
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowSources((v) => !v)}
              className="text-accent hover:underline"
            >
              {c.sources.length}건
            </button>
            {showSources && (
              <ul
                className="absolute z-10 mt-1 w-72 rounded-lg border border-border-1 bg-bg-0 p-2 text-xs shadow-lg"
              >
                {c.sources.map((u, i) => (
                  <li key={i} className="truncate">
                    <a
                      href={u}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:underline"
                    >
                      {u}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </td>
    </tr>
  );
}
