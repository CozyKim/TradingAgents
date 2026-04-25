"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
      const msg = e instanceof ApiError ? e.message : "Login failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-bg-0 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-base">TradingAgents</CardTitle>
          <p className="text-xs text-text-3">Personal trading analysis workbench</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoFocus
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={busy}
              />
            </div>
            {error && <p className="text-xs text-signal-sell">{error}</p>}
            <Button type="submit" className="w-full" disabled={busy || !password}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
