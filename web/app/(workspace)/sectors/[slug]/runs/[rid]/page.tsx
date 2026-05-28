"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";

import { PhaseProgress } from "@/components/sector/phase-progress";
import { getSectorBySlug } from "@/lib/sectors";

export default function SectorRunPage({
  params,
}: {
  params: Promise<{ slug: string; rid: string }>;
}) {
  const { slug, rid } = use(params);
  const router = useRouter();
  const qc = useQueryClient();
  const [phase, setPhase] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sector = useQuery({
    queryKey: ["sector", slug],
    queryFn: () => getSectorBySlug(slug),
  });

  useEffect(() => {
    if (!sector.data) return;
    const es = new EventSource(
      `/api/sectors/${sector.data.id}/runs/${rid}/stream`,
    );

    es.addEventListener("progress", (ev) => {
      try {
        const p = JSON.parse((ev as MessageEvent).data);
        setPhase(p.phase);
      } catch {
        // ignore malformed payload
      }
    });
    es.addEventListener("done", () => {
      setDone(true);
      es.close();
      // Invalidate so the detail page picks up the new report version.
      qc.invalidateQueries({ queryKey: ["sector-reports", sector.data!.id] });
      qc.invalidateQueries({ queryKey: ["sector-report"] });
      setTimeout(() => router.push(`/sectors/${slug}`), 800);
    });
    es.addEventListener("error", () => {
      setError("분석 도중 오류가 발생했습니다.");
      es.close();
    });
    return () => es.close();
  }, [sector.data, rid, router, slug, qc]);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10 md:px-8">
      <h1 className="mb-6 text-xl font-bold text-text-1">
        {sector.data?.name ?? "산업"} 분석 진행 중…
      </h1>
      <div className="rounded-2xl border border-border-1 bg-bg-1 p-6">
        <PhaseProgress current={phase} />
      </div>
      {done && (
        <p className="mt-4 text-emerald-600">완료! 리포트로 이동합니다…</p>
      )}
      {error && <p className="mt-4 text-signal-buy">{error}</p>}
    </div>
  );
}
