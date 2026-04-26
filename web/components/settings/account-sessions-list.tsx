"use client";
import { Button } from "@/components/ui/button";
import { useRevokeOtherSessions, useSessions } from "@/hooks/use-account";

export function AccountSessionsList() {
  const q = useSessions();
  const revoke = useRevokeOtherSessions();
  if (q.isLoading) return <p className="text-xs text-text-3">Loading…</p>;
  if (q.error)
    return (
      <p className="text-xs text-signal-sell">
        {(q.error as Error).message}
      </p>
    );
  const sessions = q.data ?? [];
  const others = sessions.filter((s) => !s.is_current).length;
  return (
    <div className="space-y-2 max-w-md">
      <ul className="text-xs text-text-2 space-y-1">
        {sessions.map((s) => (
          <li
            key={s.id_masked + s.expires_at}
            className="flex items-center justify-between gap-3 border border-border-1 rounded-md px-3 py-1.5 bg-bg-1"
          >
            <span className="font-mono">{s.id_masked}</span>
            <span className="text-text-3">
              expires {new Date(s.expires_at).toLocaleString()}
            </span>
            {s.is_current && (
              <span className="text-[10px] uppercase tracking-widest text-accent">
                current
              </span>
            )}
          </li>
        ))}
      </ul>
      <Button
        variant="outline"
        disabled={revoke.isPending || others === 0}
        onClick={() => revoke.mutate()}
      >
        {revoke.isPending ? "Revoking…" : `Revoke ${others} other session${others === 1 ? "" : "s"}`}
      </Button>
    </div>
  );
}
