"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createSector,
  getTrendingScan,
  listTrendingScans,
  openTrendingStream,
  startTrendingScan,
  type TrendingSector,
} from "@/lib/sectors";

export default function NewSectorPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const qc = useQueryClient();
  const [scanning, setScanning] = useState(false);
  const [scanStage, setScanStage] = useState<string>("");
  const [scanError, setScanError] = useState<string | null>(null);
  const [selectedScanId, setSelectedScanId] = useState<number | null>(null);
  const cancelStreamRef = useRef<(() => void) | null>(null);

  // Saved scan versions (newest first). Drives the version selector + restore.
  const scans = useQuery({
    queryKey: ["trending-scans"],
    queryFn: listTrendingScans,
  });

  // The scan to display: explicit selection, else the newest saved scan.
  const activeScanId = selectedScanId ?? scans.data?.[0]?.id ?? null;

  const activeScan = useQuery({
    queryKey: ["trending-scan", activeScanId],
    queryFn: () => getTrendingScan(activeScanId as number),
    enabled: activeScanId != null,
  });

  const trending = activeScan.data?.sectors ?? [];

  async function onScan() {
    cancelStreamRef.current?.();
    setScanning(true);
    setScanError(null);
    try {
      const { job_id } = await startTrendingScan();
      cancelStreamRef.current = openTrendingStream(job_id, {
        onProgress: (d) => setScanStage(d.message ?? d.stage ?? ""),
        onDone: async (_sectors, scanId) => {
          setScanning(false);
          // Refresh the version list, then select the freshly saved scan.
          await qc.invalidateQueries({ queryKey: ["trending-scans"] });
          if (scanId != null) setSelectedScanId(scanId);
        },
        onError: (msg) => {
          setScanError(msg);
          setScanning(false);
        },
      });
    } catch (err) {
      setScanError(err instanceof Error ? err.message : "추천 실패");
      setScanning(false);
    }
  }

  useEffect(() => () => cancelStreamRef.current?.(), []);

  function applyTrending(s: TrendingSector) {
    setName(s.name);
    setDescription(s.description);
    setKeywords([...s.keywords, ...s.tickers].join(", "));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await createSector({
        name: name.trim(),
        description: description.trim() || undefined,
        keywords: keywords
          .split(",")
          .map((k) => k.trim())
          .filter(Boolean),
      });
      router.push(`/sectors/${created.slug}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "생성 실패";
      setError(msg);
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-xl px-6 py-6 md:px-8">
      <h1 className="mb-6 text-2xl font-bold text-text-1">새 섹터</h1>

      <section className="mb-6 rounded-lg border border-border-1 bg-bg-2 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-text-1">지금 핫한 섹터 추천</p>
            <p className="text-xs text-text-3">
              한국·미국 커뮤니티와 최신 뉴스를 분석해 뜨는 테마를 찾아줍니다.
            </p>
          </div>
          <button
            type="button"
            onClick={onScan}
            disabled={scanning}
            className="shrink-0 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {scanning ? `분석 중… ${scanStage}` : "🔥 핫 섹터 추천받기"}
          </button>
        </div>

        {(scans.data?.length ?? 0) > 0 && (
          <div className="mt-3 flex items-center gap-2">
            <label className="text-xs text-text-3">버전</label>
            <select
              aria-label="스캔 버전 선택"
              value={activeScanId ?? ""}
              onChange={(e) => setSelectedScanId(Number(e.target.value))}
              className="rounded-md border border-border-1 bg-bg-1 px-2 py-1 text-xs text-text-1"
            >
              {scans.data!.map((s) => (
                <option key={s.id} value={s.id}>
                  {new Date(s.created_at).toLocaleString("ko-KR")} · {s.sector_count}개
                </option>
              ))}
            </select>
          </div>
        )}

        {scanError && <p className="mt-3 text-sm text-signal-buy">{scanError}</p>}

        {!scanning && !scanError && (scans.data?.length ?? 0) === 0 && (
          <p className="mt-3 text-sm text-text-3">
            아직 추천 기록이 없습니다. "🔥 핫 섹터 추천받기"를 눌러 시작하세요.
          </p>
        )}

        {trending.length > 0 && (
          <ul className="mt-4 space-y-2">
            {trending.map((s, i) => (
              <li
                key={`${s.name}-${i}`}
                className="rounded-lg border border-border-1 bg-bg-1 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-text-1">{s.name}</span>
                  <span className="rounded-full bg-accent/10 px-2 py-0.5 text-xs font-semibold text-accent">
                    🔥 {Math.round(s.hotness_score)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-text-3">{s.rationale}</p>
                {s.tickers.length > 0 && (
                  <p className="mt-1 text-xs text-text-3">
                    대표 종목: {s.tickers.join(", ")}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => applyTrending(s)}
                  className="mt-2 rounded-md border border-border-1 px-2 py-1 text-xs text-text-1 hover:bg-bg-2"
                >
                  이 섹터로 만들기
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <label className="mb-4 block">
        <span className="mb-1 block text-sm font-medium text-text-1">이름 *</span>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="예) 양자 컴퓨팅"
          className="w-full rounded-lg border border-border-1 bg-bg-1 px-3 py-2 text-text-1 placeholder:text-text-3"
        />
      </label>

      <label className="mb-4 block">
        <span className="mb-1 block text-sm font-medium text-text-1">설명</span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          placeholder="이 섹터가 무엇을 다루는지 한두 줄로"
          className="w-full rounded-lg border border-border-1 bg-bg-1 px-3 py-2 text-text-1 placeholder:text-text-3"
        />
      </label>

      <label className="mb-6 block">
        <span className="mb-1 block text-sm font-medium text-text-1">키워드 (쉼표 구분)</span>
        <input
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="예) IonQ, qubits, quantum supremacy"
          className="w-full rounded-lg border border-border-1 bg-bg-1 px-3 py-2 text-text-1 placeholder:text-text-3"
        />
        <span className="mt-1 block text-xs text-text-3">
          웹 검색 시드로 활용됩니다.
        </span>
      </label>

      {error && (
        <p className="mb-4 text-sm text-signal-buy">{error}</p>
      )}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={submitting || !name.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {submitting ? "생성 중…" : "생성"}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="rounded-lg border border-border-1 bg-bg-1 px-4 py-2 text-sm text-text-1 hover:bg-bg-2"
        >
          취소
        </button>
      </div>
    </form>
  );
}
