"use client";

import { humanizeCron } from "@/lib/datetime";

type Preset = { label: string; cron: string };
type PresetMap = Record<string, Preset[]>;

const PRESETS: PresetMap = {
  "Asia/Seoul": [
    { label: "매일 오전 9시", cron: "0 9 * * *" },
    { label: "매일 오후 10시", cron: "0 22 * * *" },
    { label: "평일 오전 8시", cron: "0 8 * * 1-5" },
    { label: "월요일 오전 9시", cron: "0 9 * * 1" },
  ],
  "America/New_York": [
    { label: "장 시작 직후 (평일 09:30 ET)", cron: "30 9 * * 1-5" },
    { label: "장 마감 후 (평일 16:30 ET)", cron: "30 16 * * 1-5" },
    { label: "매일 09:30 ET", cron: "30 9 * * *" },
    { label: "매주 월요일 09:00 ET", cron: "0 9 * * 1" },
  ],
  UTC: [
    { label: "매일 00:00 UTC", cron: "0 0 * * *" },
    { label: "매일 12:00 UTC", cron: "0 12 * * *" },
    { label: "평일 00:00 UTC", cron: "0 0 * * 1-5" },
  ],
};

const TZ_LABEL: Record<string, string> = {
  "Asia/Seoul": "KST",
  "America/New_York": "ET",
  UTC: "UTC",
};

export function CronHelper({
  value,
  timezone,
  onChange,
}: {
  value: string;
  timezone: string;
  onChange: (v: string) => void;
}) {
  const presets = PRESETS[timezone] ?? PRESETS["Asia/Seoul"];
  const tzLabel = TZ_LABEL[timezone] ?? timezone;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {presets.map((p) => (
          <button
            type="button"
            key={p.cron}
            onClick={() => onChange(p.cron)}
            className={`text-2xs px-2 py-1 rounded-md border ${
              value === p.cron
                ? "bg-accent/20 border-accent text-text-1"
                : "bg-bg-2 border-border-1 text-text-2 hover:text-text-1"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      {value && (
        <p className="text-2xs text-text-3">
          해석: {humanizeCron(value, { tzLabel })}
        </p>
      )}
    </div>
  );
}
