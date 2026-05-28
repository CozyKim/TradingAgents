"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { use, useState } from "react";
import ReactMarkdown from "react-markdown";

import { CandidateTickers } from "@/components/sector/candidate-tickers";
import { CompaniesTable } from "@/components/sector/companies-table";
import { ValueChainDiagram } from "@/components/sector/value-chain-diagram";
import {
  getReport,
  getSectorBySlug,
  listReports,
  startSectorRun,
} from "@/lib/sectors";

export default function SectorDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);
  const router = useRouter();
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);

  const sector = useQuery({
    queryKey: ["sector", slug],
    queryFn: () => getSectorBySlug(slug),
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

  const startRun = useMutation({
    mutationFn: () => startSectorRun(sector.data!.id),
    onSuccess: (run) => router.push(`/sectors/${slug}/runs/${run.id}`),
  });

  if (sector.isLoading) {
    return <p className="px-6 py-6 text-text-3">로딩 중…</p>;
  }
  if (!sector.data) {
    return (
      <p className="px-6 py-6 text-text-2">섹터를 찾을 수 없습니다.</p>
    );
  }

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
            disabled={startRun.isPending}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {startRun.isPending ? "시작 중…" : "리포트 새로 생성"}
          </button>
        </div>
      </header>

      {startRun.error && (
        <p className="mb-4 text-sm text-signal-buy">
          분석 시작 실패: {String(startRun.error)}
        </p>
      )}

      {reports.data && reports.data.length === 0 && !startRun.isPending && (
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
