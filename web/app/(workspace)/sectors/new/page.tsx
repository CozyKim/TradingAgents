"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createSector, openTrendingStream, startTrendingScan, type TrendingSector } from "@/lib/sectors";

export default function NewSectorPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [scanning, setScanning] = useState(false);
  const [scanStage, setScanStage] = useState<string>("");
  const [trending, setTrending] = useState<TrendingSector[]>([]);
  const [scanError, setScanError] = useState<string | null>(null);

  async function onScan() {
    setScanning(true);
    setScanError(null);
    setTrending([]);
    try {
      const { job_id } = await startTrendingScan();
      openTrendingStream(job_id, {
        onProgress: (d) => setScanStage(d.stage ?? ""),
        onDone: (sectors) => {
          setTrending(sectors);
          setScanning(false);
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

        {scanError && <p className="mt-3 text-sm text-signal-buy">{scanError}</p>}

        {trending.length > 0 && (
          <ul className="mt-4 space-y-2">
            {trending.map((s) => (
              <li
                key={s.name}
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
