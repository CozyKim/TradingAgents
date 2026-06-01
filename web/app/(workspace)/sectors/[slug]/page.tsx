"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MarkdownText } from "@/components/analysis/markdown-text";
import { CandidateTickers } from "@/components/sector/candidate-tickers";
import { CompaniesTable } from "@/components/sector/companies-table";
import { PhaseProgress } from "@/components/sector/phase-progress";
import { ValueChainDiagram } from "@/components/sector/value-chain-diagram";
import {
  cancelSectorRun,
  getActiveRun,
  getReport,
  getSectorBySlug,
  listReports,
  startSectorRun,
} from "@/lib/sectors";
import { useSectorRunStream } from "@/hooks/use-sector-run-stream";

export default function SectorDetailPage() {
  // Project is on Next.js 14.2.x where dynamic route params are a plain
  // object accessed via useParams() — NOT a Promise unwrapped by React.use().
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);
  // Outcome banner for a run that ended (cancel/fail) during this session —
  // activeRun goes null afterward, so we keep the last outcome to surface it.
  const [outcome, setOutcome] = useState<
    { kind: "cancelled" } | { kind: "failed"; error: string | null } | null
  >(null);
  const [cancelling, setCancelling] = useState(false);

  const sector = useQuery({
    queryKey: ["sector", slug],
    queryFn: () => getSectorBySlug(slug),
  });

  // Poll for an in-flight run so a user who navigates away and comes back
  // still sees "분석 진행 중" with the right phase.
  const activeRun = useQuery({
    queryKey: ["sector-active-run", sector.data?.id],
    queryFn: () => getActiveRun(sector.data!.id),
    enabled: !!sector.data,
    refetchInterval: (q) => (q.state.data ? 5_000 : 15_000),
  });

  const reports = useQuery({
    queryKey: ["sector-reports", sector.data?.id],
    queryFn: () => listReports(sector.data!.id),
    enabled: !!sector.data,
  });

  const activeReportId = selectedReportId ?? reports.data?.[0]?.id ?? null;

  const report = useQuery({
    queryKey: ["sector-report", activeReportId],
    queryFn: () => getReport(sector.data!.id, activeReportId!),
    enabled: !!sector.data && !!activeReportId,
  });

  const activeRunId = activeRun.data?.id;
  const stream = useSectorRunStream(
    sector.data?.id,
    activeRunId,
    !!activeRun.data,
  );

  // React to terminal stream states: refresh queries + surface an outcome.
  useEffect(() => {
    const sectorId = sector.data?.id;
    if (sectorId == null) return;
    if (stream.state === "completed") {
      qc.invalidateQueries({ queryKey: ["sector-reports", sectorId] });
      qc.invalidateQueries({ queryKey: ["sector-active-run", sectorId] });
      setSelectedReportId(null);
      setOutcome(null);
    } else if (stream.state === "cancelled") {
      qc.invalidateQueries({ queryKey: ["sector-active-run", sectorId] });
      setOutcome({ kind: "cancelled" });
    } else if (stream.state === "failed") {
      qc.invalidateQueries({ queryKey: ["sector-active-run", sectorId] });
      setOutcome({ kind: "failed", error: stream.error });
    }
  }, [stream.state, stream.error, sector.data?.id, qc]);

  async function onCancelActive() {
    const sectorId = sector.data?.id;
    if (sectorId == null || !activeRunId) return;
    setCancelling(true);
    try {
      await cancelSectorRun(sectorId, activeRunId);
      await qc.invalidateQueries({ queryKey: ["sector-active-run", sectorId] });
    } catch {
      // The stream's cancelled / stall handling still updates the UI.
    } finally {
      setCancelling(false);
    }
  }

  const startRun = useMutation({
    mutationFn: () => startSectorRun(sector.data!.id),
    onSuccess: (run) => {
      // Immediately refresh active-run so the UI flips to "진행 중" without
      // waiting for the next poll. The dedicated runs/[rid] page is still
      // reachable via deep link, but we keep the user on /sectors/<slug>
      // by default so backing out doesn't lose context.
      qc.setQueryData(["sector-active-run", sector.data!.id], run);
      router.push(`/sectors/${slug}/runs/${run.id}`);
    },
  });

  if (sector.isLoading) {
    return <p className="px-6 py-6 text-text-3">로딩 중…</p>;
  }
  if (!sector.data) {
    return (
      <p className="px-6 py-6 text-text-2">섹터를 찾을 수 없습니다.</p>
    );
  }

  const running = activeRun.data;

  return (
    <div className="mx-auto max-w-5xl px-6 py-6 md:px-8">
      <header className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text-1">{sector.data.name}</h1>
          {sector.data.description && (
            <p className="mt-1 text-text-2">{sector.data.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {reports.data && reports.data.length > 0 && (
            <select
              value={activeReportId ?? ""}
              onChange={(e) => setSelectedReportId(Number(e.target.value))}
              className="rounded-lg border border-border-1 bg-bg-1 px-3 py-2 text-sm"
            >
              {reports.data.map((r) => (
                <option key={r.id} value={r.id}>
                  v{r.version} · {new Date(r.created_at).toLocaleDateString("ko-KR")}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={() => startRun.mutate()}
            disabled={startRun.isPending || !!running}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            title={
              running ? "이미 분석이 진행 중입니다" : "새 리포트 생성"
            }
          >
            {startRun.isPending
              ? "시작 중…"
              : running
                ? "진행 중…"
                : "리포트 새로 생성"}
          </button>
        </div>
      </header>

      {startRun.error && (
        <p className="mb-4 text-sm text-signal-buy">
          분석 시작 실패: {String(startRun.error)}
        </p>
      )}

      {running && (
        <section className="mb-6 rounded-2xl border border-accent/40 bg-accent-muted p-5">
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <h2 className="text-sm font-semibold text-text-1">분석 진행 중</h2>
            <button
              type="button"
              onClick={() => router.push(`/sectors/${slug}/runs/${running.id}`)}
              className="text-xs text-accent hover:underline"
            >
              진행 페이지 열기 →
            </button>
          </div>
          <PhaseProgress current={stream.phase ?? running.phase} state={stream.state} />
          {stream.state === "stalled" ? (
            <p className="mt-3 text-xs text-amber-600">
              응답이 없습니다 ({Math.floor(stream.lastSignalAgoMs / 1000)}초째 신호
              없음). 분석이 멈췄을 수 있어요.
            </p>
          ) : (
            <p className="mt-3 text-xs text-text-3">
              분석 중 · {Math.floor(stream.elapsedMs / 1000)}초 경과 · 화면을 닫아도
              백그라운드에서 계속 실행됩니다.
            </p>
          )}
          <button
            type="button"
            onClick={onCancelActive}
            disabled={cancelling}
            className="mt-3 rounded-lg border border-border-1 bg-bg-1 px-3 py-1.5 text-xs text-text-1 hover:bg-bg-2 disabled:opacity-50"
          >
            {cancelling ? "취소 중…" : "분석 취소"}
          </button>
        </section>
      )}

      {outcome && !running && (
        <section className="mb-6 rounded-2xl border border-border-1 bg-bg-1 p-4">
          {outcome.kind === "cancelled" ? (
            <p className="text-text-2">직전 분석이 취소되었습니다.</p>
          ) : (
            <p className="text-signal-buy">
              직전 분석이 실패했습니다{outcome.error ? `: ${outcome.error}` : "."}
            </p>
          )}
          <button
            type="button"
            onClick={() => setOutcome(null)}
            className="mt-2 text-xs text-accent hover:underline"
          >
            닫기
          </button>
        </section>
      )}

      {reports.data &&
        reports.data.length === 0 &&
        !startRun.isPending &&
        !running && (
          <p className="rounded-lg bg-bg-1 p-6 text-text-2">
            아직 리포트가 없습니다. &ldquo;리포트 새로 생성&rdquo; 버튼으로 시작하세요.
          </p>
        )}

      {report.data && (
        <article className="space-y-8">
          <section>
            <h2 className="mb-2 text-lg font-semibold text-text-1">가치사슬</h2>
            <div className="rounded-lg border border-border-1 bg-bg-1 p-4">
              <ValueChainDiagram mermaid={report.data.value_chain_mermaid} />
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-text-1">
              단계별 핵심 기업
            </h2>
            <CompaniesTable companies={report.data.companies} />
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-text-1">
              투자 전망
            </h2>
            <div className="rounded-lg border border-border-1 bg-bg-1 p-4">
              <MarkdownText text={report.data.outlook_summary} />
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-semibold text-text-1">
              후보 종목
            </h2>
            <CandidateTickers
              candidates={report.data.candidate_tickers}
              fromSectorSlug={sector.data.slug}
              fromReportId={report.data.id}
            />
          </section>

          <details className="rounded-lg border border-border-1 bg-bg-1 p-4">
            <summary className="cursor-pointer text-sm font-medium text-text-2">
              전체 리포트 (원문 Markdown)
            </summary>
            <div className="mt-3">
              <MarkdownText text={report.data.report_md} />
            </div>
          </details>
        </article>
      )}
    </div>
  );
}
