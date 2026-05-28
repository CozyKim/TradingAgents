"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createSector } from "@/lib/sectors";

export default function NewSectorPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
