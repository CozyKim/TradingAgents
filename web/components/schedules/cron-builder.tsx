"use client";

import { useEffect, useMemo, useState } from "react";

import { humanizeCron } from "@/lib/datetime";

type Frequency = "daily" | "weekdays" | "weekly" | "custom";

const DAY_CHIPS: { value: number; label: string }[] = [
  { value: 1, label: "월" },
  { value: 2, label: "화" },
  { value: 3, label: "수" },
  { value: 4, label: "목" },
  { value: 5, label: "금" },
  { value: 6, label: "토" },
  { value: 0, label: "일" },
];

const QUICK_PRESETS_BY_TZ: Record<string, { label: string; cron: string }[]> = {
  "Asia/Seoul": [
    { label: "매일 오전 9시", cron: "0 9 * * *" },
    { label: "매일 오후 10시", cron: "0 22 * * *" },
    { label: "평일 오전 8시", cron: "0 8 * * 1-5" },
    { label: "월요일 오전 9시", cron: "0 9 * * 1" },
  ],
  "America/New_York": [
    { label: "장 시작 (평일 09:30 ET)", cron: "30 9 * * 1-5" },
    { label: "장 마감 (평일 16:30 ET)", cron: "30 16 * * 1-5" },
    { label: "매일 09:30 ET", cron: "30 9 * * *" },
    { label: "월요일 09:00 ET", cron: "0 9 * * 1" },
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

function buildCron(
  frequency: Frequency,
  hour: number,
  minute: number,
  days: number[],
): string | null {
  if (frequency === "daily") return `${minute} ${hour} * * *`;
  if (frequency === "weekdays") return `${minute} ${hour} * * 1-5`;
  if (frequency === "weekly") {
    if (days.length === 0) return null;
    const sorted = [...days].sort((a, b) => a - b);
    return `${minute} ${hour} * * ${sorted.join(",")}`;
  }
  return null;
}

type Parsed = {
  frequency: Frequency;
  hour: number;
  minute: number;
  days: number[];
};

function parseCron(expr: string): Parsed {
  const fallback: Parsed = { frequency: "custom", hour: 9, minute: 0, days: [] };
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return fallback;
  const [m, h, dom, mon, dow] = parts;
  const minute = Number(m);
  const hour = Number(h);
  if (!Number.isInteger(minute) || !Number.isInteger(hour)) return fallback;
  if (minute < 0 || minute > 59 || hour < 0 || hour > 23) return fallback;
  if (dom !== "*" || mon !== "*") return fallback;
  if (dow === "*") return { frequency: "daily", hour, minute, days: [] };
  if (dow === "1-5") return { frequency: "weekdays", hour, minute, days: [] };
  const dayList = dow.split(",").map((d) => Number(d));
  if (dayList.every((d) => Number.isInteger(d) && d >= 0 && d <= 6)) {
    return { frequency: "weekly", hour, minute, days: dayList };
  }
  return fallback;
}

export function CronBuilder({
  value,
  timezone,
  onChange,
}: {
  value: string;
  timezone: string;
  onChange: (v: string) => void;
}) {
  const initial = useMemo(() => parseCron(value), [value]);
  const [frequency, setFrequency] = useState<Frequency>(initial.frequency);
  const [hour, setHour] = useState(initial.hour);
  const [minute, setMinute] = useState(initial.minute);
  const [days, setDays] = useState<number[]>(
    initial.days.length ? initial.days : [1],
  );
  const [raw, setRaw] = useState(value);

  useEffect(() => {
    if (frequency === "custom") return;
    const next = buildCron(frequency, hour, minute, days);
    if (next && next !== value) onChange(next);
    if (next) setRaw(next);
  }, [frequency, hour, minute, days]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (value !== raw) setRaw(value);
  }, [value, raw]);

  const tzLabel = TZ_LABEL[timezone] ?? timezone;
  const presets = QUICK_PRESETS_BY_TZ[timezone] ?? QUICK_PRESETS_BY_TZ["Asia/Seoul"];

  const toggleDay = (d: number) =>
    setDays((cur) =>
      cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d],
    );

  const applyPreset = (cron: string) => {
    const parsed = parseCron(cron);
    setFrequency(parsed.frequency);
    if (parsed.frequency !== "custom") {
      setHour(parsed.hour);
      setMinute(parsed.minute);
      if (parsed.days.length) setDays(parsed.days);
    }
    onChange(cron);
    setRaw(cron);
  };

  const onRawChange = (next: string) => {
    setRaw(next);
    onChange(next);
    const parsed = parseCron(next);
    setFrequency(parsed.frequency);
    if (parsed.frequency !== "custom") {
      setHour(parsed.hour);
      setMinute(parsed.minute);
      if (parsed.days.length) setDays(parsed.days);
    }
  };

  return (
    <div className="space-y-3 border border-border-1 rounded-md p-3 bg-bg-1">
      <div>
        <div className="text-xs text-text-2 mb-1">반복</div>
        <div className="flex flex-wrap gap-1">
          {(
            [
              { value: "daily", label: "매일" },
              { value: "weekdays", label: "평일" },
              { value: "weekly", label: "특정 요일" },
              { value: "custom", label: "직접 입력" },
            ] as { value: Frequency; label: string }[]
          ).map((f) => (
            <button
              type="button"
              key={f.value}
              onClick={() => setFrequency(f.value)}
              className={`text-xs px-3 py-1 rounded-md border ${
                frequency === f.value
                  ? "bg-accent/20 border-accent text-text-1"
                  : "bg-bg-2 border-border-1 text-text-2 hover:text-text-1"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {frequency === "weekly" && (
        <div>
          <div className="text-xs text-text-2 mb-1">요일</div>
          <div className="flex flex-wrap gap-1">
            {DAY_CHIPS.map((d) => (
              <button
                type="button"
                key={d.value}
                onClick={() => toggleDay(d.value)}
                aria-pressed={days.includes(d.value)}
                className={`w-9 h-8 text-xs rounded-md border ${
                  days.includes(d.value)
                    ? "bg-accent/20 border-accent text-text-1"
                    : "bg-bg-2 border-border-1 text-text-2 hover:text-text-1"
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {frequency !== "custom" && (
        <div>
          <div className="text-xs text-text-2 mb-1">시각 ({tzLabel})</div>
          <div className="flex items-center gap-2">
            <select
              value={hour}
              onChange={(e) => setHour(Number(e.target.value))}
              aria-label="시"
              className="bg-bg-2 border border-border-1 rounded-md px-2 py-1.5 text-sm font-mono"
            >
              {Array.from({ length: 24 }, (_, i) => (
                <option key={i} value={i}>
                  {String(i).padStart(2, "0")}
                </option>
              ))}
            </select>
            <span className="text-text-3">:</span>
            <select
              value={minute}
              onChange={(e) => setMinute(Number(e.target.value))}
              aria-label="분"
              className="bg-bg-2 border border-border-1 rounded-md px-2 py-1.5 text-sm font-mono"
            >
              {[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55].map((m) => (
                <option key={m} value={m}>
                  {String(m).padStart(2, "0")}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      <div>
        <div className="text-xs text-text-2 mb-1">Cron 표현식</div>
        <input
          type="text"
          value={raw}
          onChange={(e) => onRawChange(e.target.value)}
          className="w-full bg-bg-2 border border-border-1 rounded-md px-2 py-1.5 text-sm font-mono"
          placeholder="0 9 * * *"
        />
        <p className="text-2xs text-text-3 mt-1">
          해석: {humanizeCron(raw, { tzLabel })}
        </p>
      </div>

      <div>
        <div className="text-xs text-text-2 mb-1">자주 쓰는 설정</div>
        <div className="flex flex-wrap gap-1">
          {presets.map((p) => (
            <button
              type="button"
              key={p.cron}
              onClick={() => applyPreset(p.cron)}
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
      </div>
    </div>
  );
}
