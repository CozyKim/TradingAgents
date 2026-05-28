import Link from "next/link";

import type { SectorSummary } from "@/lib/sectors";

interface Props {
  sector: SectorSummary;
}

export function SectorCard({ sector }: Props) {
  const latest = sector.latest_report_at
    ? new Date(sector.latest_report_at).toLocaleDateString("ko-KR")
    : "리포트 없음";
  return (
    <Link
      href={`/sectors/${sector.slug}`}
      className="block rounded-2xl border border-border-1 bg-bg-1 p-5 shadow-card transition hover:border-accent"
    >
      <div className="flex items-baseline justify-between">
        <h3 className="text-lg font-semibold text-text-1">{sector.name}</h3>
        {sector.is_preset && (
          <span className="text-xs text-text-3">프리셋</span>
        )}
      </div>
      {sector.description && (
        <p className="mt-1 text-sm text-text-2 line-clamp-2">{sector.description}</p>
      )}
      <div className="mt-3 flex items-center gap-2 text-xs text-text-3">
        <span>최신 리포트: {latest}</span>
        {sector.latest_report_version != null && (
          <span>v{sector.latest_report_version}</span>
        )}
      </div>
    </Link>
  );
}
