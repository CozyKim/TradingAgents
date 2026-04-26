"use client";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useChangePassword } from "@/hooks/use-account";

export function AccountPasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [revoke, setRevoke] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const m = useChangePassword();

  return (
    <form
      className="space-y-3 max-w-md"
      onSubmit={async (e) => {
        e.preventDefault();
        setMsg(null);
        try {
          await m.mutateAsync({
            current_password: current,
            new_password: next,
            revoke_other_sessions: revoke,
          });
          setCurrent("");
          setNext("");
          setMsg("Password updated.");
        } catch (err) {
          setMsg((err as Error).message);
        }
      }}
    >
      <div className="space-y-1">
        <Label htmlFor="cur">Current password</Label>
        <Input
          id="cur"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="new">New password (≥ 8 chars)</Label>
        <Input
          id="new"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          minLength={8}
        />
      </div>
      <label className="flex items-center gap-2 text-xs text-text-2">
        <Switch checked={revoke} onCheckedChange={setRevoke} />
        Revoke all other sessions
      </label>
      <Button type="submit" disabled={m.isPending}>
        {m.isPending ? "Saving…" : "Update password"}
      </Button>
      {msg && <p className="text-xs text-text-2">{msg}</p>}
    </form>
  );
}
