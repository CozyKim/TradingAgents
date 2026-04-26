"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUpdateSchedule } from "@/hooks/use-schedules";
import { Schedule } from "@/lib/schedules";

import { CronBuilder } from "./cron-builder";

const TZ_OPTIONS: { value: string; label: string }[] = [
  { value: "Asia/Seoul", label: "한국 (KST, UTC+9)" },
  { value: "America/New_York", label: "미국 동부 (ET)" },
  { value: "UTC", label: "UTC" },
];

export function ScheduleEditRow({
  schedule,
  onClose,
}: {
  schedule: Schedule;
  onClose: () => void;
}) {
  const [name, setName] = useState(schedule.name);
  const [cron, setCron] = useState(schedule.cron_expr);
  const [tz, setTz] = useState(schedule.timezone);
  const upd = useUpdateSchedule();

  const dirty =
    name !== schedule.name ||
    cron !== schedule.cron_expr ||
    tz !== schedule.timezone;

  const save = async () => {
    if (!dirty) {
      onClose();
      return;
    }
    await upd.mutateAsync({
      id: schedule.id,
      payload: {
        name,
        cron_expr: cron,
        timezone: tz,
      },
    });
    onClose();
  };

  return (
    <div className="flex flex-col gap-3 p-3 bg-bg-2/40 border border-border-1 rounded-md">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <Label htmlFor={`name-${schedule.id}`}>이름</Label>
          <Input
            id={`name-${schedule.id}`}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor={`tz-${schedule.id}`}>타임존</Label>
          <select
            id={`tz-${schedule.id}`}
            value={tz}
            onChange={(e) => setTz(e.target.value)}
            className="w-full bg-bg-1 border border-border-1 rounded-md px-3 py-2 text-sm"
          >
            {TZ_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <Label>스케줄</Label>
        <CronBuilder value={cron} timezone={tz} onChange={setCron} />
      </div>

      <div className="flex items-center justify-end gap-2">
        {upd.error && (
          <p className="text-xs text-neg mr-auto">
            {(upd.error as Error).message}
          </p>
        )}
        <Button variant="ghost" size="sm" onClick={onClose} disabled={upd.isPending}>
          취소
        </Button>
        <Button size="sm" onClick={save} disabled={upd.isPending}>
          {upd.isPending ? "저장 중…" : "저장"}
        </Button>
      </div>
    </div>
  );
}
