"use client";

const PRESETS: { label: string; cron: string }[] = [
  { label: "Daily 09:30 ET", cron: "30 9 * * *" },
  { label: "Daily 16:30 ET", cron: "30 16 * * *" },
  { label: "Weekdays 16:30 ET", cron: "30 16 * * 1-5" },
  { label: "Mon 09:00 ET", cron: "0 9 * * 1" },
];

export function CronHelper({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {PRESETS.map((p) => (
        <button
          type="button"
          key={p.cron}
          onClick={() => onChange(p.cron)}
          className={`text-[10px] px-2 py-1 rounded-md border ${
            value === p.cron
              ? "bg-accent/20 border-accent text-text-1"
              : "bg-bg-2 border-border-1 text-text-2 hover:text-text-1"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
