"use client";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useRestore } from "@/hooks/use-account";

export function AccountRestoreForm() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const m = useRestore();

  return (
    <form
      className="space-y-2 max-w-md"
      onSubmit={async (e) => {
        e.preventDefault();
        const f = inputRef.current?.files?.[0];
        if (!f) {
          setMsg("Choose a .db file first.");
          return;
        }
        if (
          !window.confirm(
            "This will replace ALL current data and sign you out everywhere. Continue?",
          )
        )
          return;
        setMsg(null);
        try {
          await m.mutateAsync(f);
          setMsg("Restore complete. Redirecting…");
          setTimeout(() => window.location.assign("/login"), 800);
        } catch (err) {
          setMsg((err as Error).message);
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".db,application/octet-stream"
        className="block w-full text-xs text-text-2"
      />
      <Button type="submit" variant="destructive" disabled={m.isPending}>
        {m.isPending ? "Restoring…" : "Restore from file"}
      </Button>
      {msg && <p className="text-xs text-text-2">{msg}</p>}
    </form>
  );
}
