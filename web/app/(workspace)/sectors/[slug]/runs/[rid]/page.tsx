"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PhaseProgress } from "@/components/sector/phase-progress";
import { useSectorRunStream } from "@/hooks/use-sector-run-stream";
import { cancelSectorRun, getSectorBySlug } from "@/lib/sectors";

export default function SectorRunPage() {
  // Next.js 14.2.x — params is a plain object via useParams(), not a Promise.
  const { slug, rid } = useParams<{ slug: string; rid: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [cancelling, setCancelling] = useState(false);

  const sector = useQuery({
    queryKey: ["sector", slug],
    queryFn: () => getSectorBySlug(slug),
  });
  const sectorId = sector.data?.id;

  const stream = useSectorRunStream(sectorId, rid, !!sectorId);

  // On completion, refresh report queries then bounce back to the detail page.
  useEffect(() => {
    if (stream.state !== "completed" || sectorId == null) return;
    qc.invalidateQueries({ queryKey: ["sector-reports", sectorId] });
    qc.invalidateQueries({ queryKey: ["sector-report"] });
    const t = setTimeout(() => router.push(`/sectors/${slug}`), 800);
    return () => clearTimeout(t);
  }, [stream.state, sectorId, slug, router, qc]);

  async function onCancel() {
    if (sectorId == null) return;
    setCancelling(true);
    try {
      await cancelSectorRun(sectorId, rid);
    } catch {
      // The stream's cancelled / stall handling still updates the UI.
    } finally {
      // Re-enable the button if the request failed; on success the run flips
      // to "cancelled" and this control unmounts anyway.
      setCancelling(false);
    }
  }

  const elapsedSec = Math.floor(stream.elapsedMs / 1000);
  const agoSec = Math.floor(stream.lastSignalAgoMs / 1000);
  const active = stream.state === "running" || stream.state === "stalled";

  return (
    <div className="mx-auto max-w-3xl px-6 py-10 md:px-8">
      <h1 className="mb-6 text-xl font-bold text-text-1">
        {sector.data?.name ?? "산업"} 분석 진행 중…
      </h1>
      <div className="rounded-2xl border border-border-1 bg-bg-1 p-6">
        <PhaseProgress current={stream.phase} state={stream.state} />

        {stream.state === "running" && (
          <p className="mt-4 text-sm text-text-3">분석 중 · {elapsedSec}초 경과</p>
        )}
        {stream.state === "stalled" && (
          <div className="mt-4 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3">
            <p className="text-sm text-amber-600">
              응답이 없습니다 ({agoSec}초째 신호 없음). 분석이 멈췄을 수 있어요.
            </p>
          </div>
        )}

        {active && (
          <button
            type="button"
            onClick={onCancel}
            disabled={cancelling}
            className="mt-4 rounded-lg border border-border-1 px-3 py-2 text-sm text-text-1 hover:bg-bg-2 disabled:opacity-50"
          >
            {cancelling ? "취소 중…" : "분석 취소"}
          </button>
        )}
      </div>

      {stream.state === "completed" && (
        <p className="mt-4 text-emerald-600">완료! 리포트로 이동합니다…</p>
      )}
      {stream.state === "cancelled" && (
        <div className="mt-4 rounded-lg border border-border-1 bg-bg-1 p-4">
          <p className="text-text-2">분석이 취소되었습니다.</p>
          <button
            type="button"
            onClick={() => router.push(`/sectors/${slug}`)}
            className="mt-2 text-sm text-accent hover:underline"
          >
            섹터로 돌아가기 →
          </button>
        </div>
      )}
      {stream.state === "failed" && (
        <div className="mt-4 rounded-lg border border-signal-buy/40 bg-bg-1 p-4">
          <p className="text-signal-buy">
            분석 도중 오류가 발생했습니다
            {stream.error ? `: ${stream.error}` : "."}
          </p>
          <button
            type="button"
            onClick={() => router.push(`/sectors/${slug}`)}
            className="mt-2 text-sm text-accent hover:underline"
          >
            섹터로 돌아가기 →
          </button>
        </div>
      )}
    </div>
  );
}
