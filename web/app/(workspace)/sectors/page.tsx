"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { SectorCard } from "@/components/sector/sector-card";
import { listSectors } from "@/lib/sectors";

export default function SectorsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["sectors"],
    queryFn: listSectors,
  });

  return (
    <div className="px-6 py-6 md:px-8">
      <div className="mb-6 flex items-baseline justify-between">
        <h1 className="text-2xl font-bold text-text-1">산업 · 섹터</h1>
        <Link
          href="/sectors/new"
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          + 새 섹터
        </Link>
      </div>

      {isLoading && <p className="text-text-3">로딩 중…</p>}
      {error && <p className="text-signal-buy">로드 실패: {String(error)}</p>}

      {data && data.length === 0 && !isLoading && (
        <p className="rounded-lg bg-bg-1 p-6 text-text-2">
          아직 섹터가 없습니다. &quot;+ 새 섹터&quot;로 시작하세요.
        </p>
      )}

      {data && data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data.map((s) => <SectorCard key={s.id} sector={s} />)}
        </div>
      )}
    </div>
  );
}
