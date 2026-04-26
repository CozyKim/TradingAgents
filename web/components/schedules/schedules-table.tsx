"use client";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  useDeleteSchedule,
  useRunScheduleNow,
  useUpdateSchedule,
} from "@/hooks/use-schedules";
import { Schedule } from "@/lib/schedules";

function fmt(d: string | null) {
  return d ? new Date(d).toLocaleString() : "—";
}

export function SchedulesTable({ rows }: { rows: Schedule[] }) {
  const upd = useUpdateSchedule();
  const del = useDeleteSchedule();
  const run = useRunScheduleNow();
  if (rows.length === 0)
    return (
      <p className="text-sm text-text-3 py-8 text-center">No schedules yet.</p>
    );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] uppercase tracking-wider text-text-3 border-b border-border-1">
            <th className="text-left py-2">Name</th>
            <th>Ticker</th>
            <th>Cron</th>
            <th>Source</th>
            <th>Next run</th>
            <th>Last run</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id} className="border-b border-border-1 hover:bg-bg-2">
              <td className="py-2">{s.name}</td>
              <td className="font-mono text-xs">{s.ticker}</td>
              <td className="font-mono text-xs">{s.cron_expr}</td>
              <td className="text-xs text-text-3">{s.source}</td>
              <td className="text-xs">{fmt(s.next_run)}</td>
              <td className="text-xs">{fmt(s.last_run)}</td>
              <td className="text-center">
                <Switch
                  checked={s.active}
                  disabled={upd.isPending}
                  onCheckedChange={(v) =>
                    upd.mutate({ id: s.id, payload: { active: v } })
                  }
                />
              </td>
              <td className="text-right space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={run.isPending}
                  onClick={() => run.mutate(s.id)}
                >
                  Run now
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={del.isPending || s.source === "holding"}
                  onClick={() => del.mutate(s.id)}
                >
                  Delete
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
