"use client";
import { Switch } from "@/components/ui/switch";
import { useUpdateHolding } from "@/hooks/use-holdings";

export function MonitorToggle({
  holdingId,
  enabled,
}: {
  holdingId: number;
  enabled: boolean;
}) {
  const m = useUpdateHolding();
  return (
    <Switch
      checked={enabled}
      disabled={m.isPending}
      onCheckedChange={(v) =>
        m.mutate({ id: holdingId, payload: { monitor_enabled: v } })
      }
    />
  );
}
