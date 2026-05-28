"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

import { CandidateTickers } from "@/components/sector/candidate-tickers";
import { CompaniesTable } from "@/components/sector/companies-table";
import { PhaseProgress } from "@/components/sector/phase-progress";
import { ValueChainDiagram } from "@/components/sector/value-chain-diagram";
import {
  getActiveRun,
  getReport,
  getSectorBySlug,
  listReports,
  startSectorRun,
} from "@/lib/sectors";

export default function SectorDetailPage() {
  // Project is on Next.js 14.2.x where dynamic route params are a plain
  // object accessed via useParams() — NOT a Promise unwrapped by React.use().
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);
  // SSE-driven phase indicator for any active run. Initially null; populated
  // both from the bus history replay (when we re-subscribe after navigating
  // back to the page) and from live events.
  const [livePhase, setLivePhase] = useState<string | null>(null);

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

  // Re-subscribe to the SSE stream whenever there's a live run. EventBus
  // history replay means we get the latest phase even if the run started
  // before this component mounted (user clicked away and came back).
  useEffect(() => {
    if (!sector.data || !activeRun.data) {
      setLivePhase(null);
      return;
    }
    const sectorId = sector.data.id;
    const runId = activeRun.data.id;
    const es = new EventSource(
      `/api/sectors/${sectorId}/runs/${runId}/stream`,
    );
    es.addEventListener("progress", (ev) => {
      try {
        const p = JSON.parse((ev as MessageEvent).data);
        if (typeof p.phase === "string") setLivePhase(p.phase);
      } catch {
        // ignore malformed payload
      }
    });
    es.addEventListener("done", () => {
      es.close();
      // Refresh the run list, reports list, and the active-run query so
      // the page swaps from "진행 중" → new report visible.
      qc.invalidateQueries({ queryKey: ["sector-reports", sectorId] });
      qc.invalidateQueries({ queryKey: ["sector-active-run", sectorId] });
      // Auto-pick the new latest report (most recent created_at).
      setSelectedReportId(null);
    });
    es.addEventListener("error", () => {
      // Stream closed (run finished or network blip). Let polling pick up
      // the post-completion state via getActiveRun.
      es.close();
    });
    return () => es.close();
  }, [sector.data, activeRun.data, qc]);

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
            <h2 className="text-sm font-semibold text-text-1">
              분석 진행 중
            </h2>
            <button
              type="button"
              onClick={() =>
                router.push(`/sectors/${slug}/runs/${running.id}`)
              }
              className="text-xs text-accent hover:underline"
            >
              진행 페이지 열기 →
            </button>
          </div>
          <PhaseProgress current={livePhase ?? running.phase} />
          <p className="mt-3 text-xs text-text-3">
            화면을 닫아도 백그라운드에서 계속 실행됩니다. 완료되면
            새 버전이 자동으로 추가됩니다.
          </p>
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
            <div className="prose prose-sm dark:prose-invert max-w-none rounded-lg border border-border-1 bg-bg-1 p-4">
              <ReactMarkdown>{report.data.outlook_summary}</ReactMarkdown>
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
            <div className="prose prose-sm dark:prose-invert mt-3 max-w-none">
              <ReactMarkdown>{report.data.report_md}</ReactMarkdown>
            </div>
          </details>
        </article>
      )}
    </div>
  );
}
