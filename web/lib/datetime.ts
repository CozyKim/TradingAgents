import cronstrue from "cronstrue/i18n";
import "cronstrue/locales/ko";

const TZ = "Asia/Seoul";
const LOCALE = "ko-KR";

const dateTimeFmt = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const dateFmt = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TZ,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const timeFmt = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TZ,
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function toDate(value: string | number | Date | null | undefined): Date | null {
  if (value == null || value === "") return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatKST(value: string | number | Date | null | undefined, fallback = "—"): string {
  const d = toDate(value);
  return d ? dateTimeFmt.format(d) : fallback;
}

export function formatKSTDate(value: string | number | Date | null | undefined, fallback = "—"): string {
  const d = toDate(value);
  return d ? dateFmt.format(d) : fallback;
}

export function formatKSTTime(value: string | number | Date | null | undefined, fallback = "—"): string {
  const d = toDate(value);
  return d ? timeFmt.format(d) : fallback;
}

export function todayKST(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  return parts;
}

export function humanizeCron(expr: string, opts?: { tzLabel?: string }): string {
  try {
    const text = cronstrue.toString(expr, { locale: "ko", use24HourTimeFormat: true });
    return opts?.tzLabel ? `${text} (${opts.tzLabel})` : text;
  } catch {
    return expr;
  }
}
