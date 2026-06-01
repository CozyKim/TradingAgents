"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelTrendingScan,
  createSector,
  getTrendingScan,
  listTrendingScans,
  openTrendingStream,
  startTrendingScan,
  type TrendingSector,
} from "@/lib/sectors";
import { STALL_MS } from "@/lib/run-liveness";

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
  const [scanStalled, setScanStalled] = useState(false);
  const [selectedScanId, setSelectedScanId] = useState<number | null>(null);
  const cancelStreamRef = useRef<(() => void) | null>(null);
  const jobIdRef = useRef<string | null>(null);
  const lastSignalRef = useRef<number>(0);

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
    setScanStalled(false);
    lastSignalRef.current = Date.now();
    try {
      const { job_id } = await startTrendingScan();
      jobIdRef.current = job_id;
      cancelStreamRef.current = openTrendingStream(job_id, {
        onProgress: (d) => {
          lastSignalRef.current = Date.now();
          setScanStalled(false);
          setScanStage(d.message ?? d.stage ?? "");
        },
        onHeartbeat: () => {
          lastSignalRef.current = Date.now();
          setScanStalled(false);
        },
        onDone: async (_sectors, scanId) => {
          setScanning(false);
          await qc.invalidateQueries({ queryKey: ["trending-scans"] });
          if (scanId != null) {
            setSelectedScanId(scanId);
          } else {
            setScanError(
              "이번 추천에서는 새로운 핫 섹터를 찾지 못했습니다. 잠시 후 다시 시도해 주세요.",
            );
          }
        },
        onCancelled: () => {
          setScanning(false);
          setScanStage("");
          setScanStalled(false);
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

  function teardownScan() {
    cancelStreamRef.current?.();
    setScanning(false);
    setScanStage("");
    setScanStalled(false);
  }

  async function onCancelScan() {
    const jobId = jobIdRef.current;
    if (!jobId) {
      // 서버측 잡이 아직 없으면 화면만 정리한다.
      teardownScan();
      return;
    }
    try {
      await cancelTrendingScan(jobId);
    } catch (err) {
      // 백엔드 취소가 실패하면 스트림/진행 상태를 그대로 둬 잡을 방치하지 않고,
      // 오류를 노출해 재시도할 수 있게 한다.
      setScanError(err instanceof Error ? err.message : "취소 실패");
      return;
    }
    // 취소 수락됨(`cancelled` SSE 이벤트도 곧 도착). 화면을 정리한다.
    teardownScan();
  }

  useEffect(() => () => cancelStreamRef.current?.(), []);

  // While scanning, flip to "응답 없음" if no signal arrives for STALL_MS.
  useEffect(() => {
    if (!scanning) return;
    const id = setInterval(() => {
      if (Date.now() - lastSignalRef.current > STALL_MS) setScanStalled(true);
    }, 1_000);
    return () => clearInterval(id);
  }, [scanning]);

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
          {scanning ? (
            <div className="flex shrink-0 items-center gap-2">
              <span className="text-sm text-text-3">분석 중… {scanStage}</span>
              <button
                type="button"
                onClick={onCancelScan}
                className="rounded-lg border border-border-1 px-3 py-2 text-sm text-text-1 hover:bg-bg-2"
              >
                취소
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={onScan}
              className="shrink-0 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              🔥 핫 섹터 추천받기
            </button>
          )}
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

        {scanning && scanStalled && (
          <p className="mt-3 text-sm text-amber-600">
            응답이 없습니다. 추천이 멈췄을 수 있어요. "취소" 후 다시 시도해 주세요.
          </p>
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
