"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api("/api/auth/login", { method: "POST", body: JSON.stringify({ password }) });
      router.replace("/");
      router.refresh();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "로그인에 실패했어요";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center bg-bg-0 px-4">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-0 h-72 bg-[radial-gradient(60%_60%_at_50%_0%,rgba(49,130,246,0.10),transparent_70%)]"
      />
      <div className="relative z-10 w-full max-w-[380px]">
        <div className="mb-6 flex flex-col items-center text-center">
          <span
            aria-hidden
            className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent text-[24px] font-black text-white shadow-pop"
            style={{ letterSpacing: "-0.05em" }}
          >
            T
          </span>
          <h1 className="display mt-4 text-[26px] leading-[1.2] text-text-1">
            TradingAgents
          </h1>
          <p className="mt-1.5 text-[13.5px] font-medium tracking-[-0.01em] text-text-3">
            나만의 트레이딩 분석 워크벤치
          </p>
        </div>

        <div className="rounded-2xl bg-bg-1 p-6 shadow-card">
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="password">비밀번호</Label>
              <Input
                id="password"
                type="password"
                autoFocus
                autoComplete="current-password"
                placeholder="비밀번호를 입력해주세요"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={busy}
              />
            </div>
            {error && (
              <div className="rounded-xl bg-signal-sell/10 px-4 py-3 text-[13px] font-semibold text-signal-sell">
                {error}
              </div>
            )}
            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={busy || !password}
            >
              {busy ? "로그인 중…" : "로그인"}
            </Button>
          </form>
        </div>
      </div>
    </main>
  );
}
