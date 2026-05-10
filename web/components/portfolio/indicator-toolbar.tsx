"use client";
import { Settings2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ChartSettings } from "@/lib/chart-settings";
import { cn } from "@/lib/utils";
import { INDICATOR_COLORS } from "./indicator-colors";

interface ChipDef {
  key: string;
  label: string;
  active: boolean;
  color: string;
  onToggle: () => void;
}

export function IndicatorToolbar({
  settings,
  onChange,
  onReset,
}: {
  settings: ChartSettings;
  onChange: (next: ChartSettings) => void;
  onReset: () => void;
}) {
  const ov = settings.overlays;
  const pa = settings.panels;

  const update = <K extends keyof ChartSettings>(
    section: K,
    next: ChartSettings[K],
  ): ChartSettings => ({ ...settings, [section]: next });

  const chips: ChipDef[] = [
    {
      key: "sma",
      label: "SMA",
      active: ov.sma.on,
      color: INDICATOR_COLORS.sma,
      onToggle: () =>
        onChange(
          update("overlays", { ...ov, sma: { ...ov.sma, on: !ov.sma.on } }),
        ),
    },
    {
      key: "ema",
      label: `EMA${ov.ema.period}`,
      active: ov.ema.on,
      color: INDICATOR_COLORS.ema,
      onToggle: () =>
        onChange(
          update("overlays", { ...ov, ema: { ...ov.ema, on: !ov.ema.on } }),
        ),
    },
    {
      key: "bb",
      label: "BB",
      active: ov.bollinger.on,
      color: INDICATOR_COLORS.bbBand,
      onToggle: () =>
        onChange(
          update("overlays", {
            ...ov,
            bollinger: { ...ov.bollinger, on: !ov.bollinger.on },
          }),
        ),
    },
    {
      key: "rsi",
      label: "RSI",
      active: pa.rsi.on,
      color: INDICATOR_COLORS.rsi,
      onToggle: () =>
        onChange(
          update("panels", { ...pa, rsi: { ...pa.rsi, on: !pa.rsi.on } }),
        ),
    },
    {
      key: "stoch",
      label: "Stoch",
      active: pa.stoch.on,
      color: INDICATOR_COLORS.stochK,
      onToggle: () =>
        onChange(
          update("panels", { ...pa, stoch: { ...pa.stoch, on: !pa.stoch.on } }),
        ),
    },
  ];

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((c) => (
        <button
          key={c.key}
          type="button"
          onClick={c.onToggle}
          className={cn(
            "shrink-0 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-mono transition-colors",
            c.active
              ? "border-border-2 bg-bg-2 text-text-1"
              : "border-border-1 text-text-3 hover:bg-bg-2/50",
          )}
          aria-pressed={c.active}
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: c.active ? c.color : "transparent", boxShadow: c.active ? "none" : `inset 0 0 0 1px ${c.color}` }}
          />
          {c.label}
        </button>
      ))}
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Indicator parameters"
            className="h-8 w-8 shrink-0"
          >
            <Settings2 className="h-4 w-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-80">
          <ParameterForm
            settings={settings}
            onChange={onChange}
            onReset={onReset}
          />
        </PopoverContent>
      </Popover>
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
}) {
  return (
    <label className="flex items-center justify-between gap-2 text-xs">
      <span className="text-text-2">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step ?? 1}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (Number.isFinite(n) && n >= min && n <= max) onChange(n);
        }}
        className="h-7 w-16 rounded-sm border border-border-2 bg-bg-2 px-2 text-right font-mono text-xs text-text-1 outline-none focus:border-accent"
      />
    </label>
  );
}

function ParameterForm({
  settings,
  onChange,
  onReset,
}: {
  settings: ChartSettings;
  onChange: (next: ChartSettings) => void;
  onReset: () => void;
}) {
  const ov = settings.overlays;
  const pa = settings.panels;
  return (
    <div className="flex flex-col gap-3">
      <Section title="Overlays">
        {/*
          SMA는 5/20/60/120 4고정 기간을 단일 on/off 토글로 함께 관리한다.
          (period 필드는 schema/localStorage 호환을 위해 남겨두지만 UI에서는 노출하지 않음.)
        */}
        <NumberField
          label="EMA period"
          value={ov.ema.period}
          min={2}
          max={200}
          onChange={(v) =>
            onChange({
              ...settings,
              overlays: { ...ov, ema: { ...ov.ema, period: v } },
            })
          }
        />
        <NumberField
          label="Bollinger period"
          value={ov.bollinger.period}
          min={2}
          max={200}
          onChange={(v) =>
            onChange({
              ...settings,
              overlays: {
                ...ov,
                bollinger: { ...ov.bollinger, period: v },
              },
            })
          }
        />
        <NumberField
          label="Bollinger stddev"
          value={ov.bollinger.stddev}
          min={0.5}
          max={5}
          step={0.1}
          onChange={(v) =>
            onChange({
              ...settings,
              overlays: {
                ...ov,
                bollinger: { ...ov.bollinger, stddev: v },
              },
            })
          }
        />
      </Section>
      <Section title="RSI">
        <NumberField
          label="period"
          value={pa.rsi.period}
          min={2}
          max={100}
          onChange={(v) =>
            onChange({
              ...settings,
              panels: { ...pa, rsi: { ...pa.rsi, period: v } },
            })
          }
        />
      </Section>
      <Section title="Stochastic Slow">
        <NumberField
          label="%K period"
          value={pa.stoch.k}
          min={2}
          max={100}
          onChange={(v) =>
            onChange({
              ...settings,
              panels: { ...pa, stoch: { ...pa.stoch, k: v } },
            })
          }
        />
        <NumberField
          label="slowing"
          value={pa.stoch.slowing}
          min={1}
          max={20}
          onChange={(v) =>
            onChange({
              ...settings,
              panels: { ...pa, stoch: { ...pa.stoch, slowing: v } },
            })
          }
        />
        <NumberField
          label="%D period"
          value={pa.stoch.d}
          min={1}
          max={20}
          onChange={(v) =>
            onChange({
              ...settings,
              panels: { ...pa, stoch: { ...pa.stoch, d: v } },
            })
          }
        />
      </Section>
      <div className="flex justify-between border-t border-border-1 pt-2">
        <span className="text-2xs uppercase tracking-widest text-text-3">
          v1 settings
        </span>
        <button
          type="button"
          onClick={onReset}
          className="text-xs text-text-2 hover:text-text-1 hover:underline"
        >
          Reset to defaults
        </button>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-2xs uppercase tracking-widest text-text-3">
        {title}
      </div>
      <div className="flex flex-col gap-1">{children}</div>
    </div>
  );
}

