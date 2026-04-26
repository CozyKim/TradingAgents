"use client";
import { Fragment, useState } from "react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  useDeleteSchedule,
  useRunScheduleNow,
  useUpdateSchedule,
} from "@/hooks/use-schedules";
import { Schedule } from "@/lib/schedules";
import { formatKST, humanizeCron } from "@/lib/datetime";

import { ScheduleEditRow } from "./schedule-edit-row";

const TZ_LABEL: Record<string, string> = {
  "Asia/Seoul": "KST",
  "America/New_York": "ET",
  UTC: "UTC",
};

function tzLabel(tz: string): string {
  return TZ_LABEL[tz] ?? tz;
}

export function SchedulesTable({ rows }: { rows: Schedule[] }) {
  const upd = useUpdateSchedule();
  const del = useDeleteSchedule();
  const run = useRunScheduleNow();
  const [editingId, setEditingId] = useState<number | null>(null);

  if (rows.length === 0)
    return (
      <p className="text-sm text-text-3 py-8 text-center">No schedules yet.</p>
    );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-2xs uppercase tracking-wider text-text-3 border-b border-border-1">
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
          {rows.map((s) => {
            const isEditing = editingId === s.id;
            return (
              <Fragment key={s.id}>
                <tr className="border-b border-border-1 hover:bg-bg-2">
                  <td className="py-2">{s.name}</td>
                  <td className="font-mono text-xs">{s.ticker}</td>
                  <td className="text-xs">
                    <div>
                      {humanizeCron(s.cron_expr, { tzLabel: tzLabel(s.timezone) })}
                    </div>
                    <div className="font-mono text-2xs text-text-3">
                      {s.cron_expr}
                    </div>
                  </td>
                  <td className="text-xs text-text-3">{s.source}</td>
                  <td className="text-xs">{formatKST(s.next_run)}</td>
                  <td className="text-xs">{formatKST(s.last_run)}</td>
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
                      onClick={() =>
                        setEditingId(isEditing ? null : s.id)
                      }
                    >
                      {isEditing ? "닫기" : "편집"}
                    </Button>
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
                {isEditing && (
                  <tr className="border-b border-border-1">
                    <td colSpan={8} className="p-3">
                      <ScheduleEditRow
                        schedule={s}
                        onClose={() => setEditingId(null)}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
