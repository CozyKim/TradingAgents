"use client";
import { useCallback, useEffect, useState } from "react";
import {
  ChartSettings,
  DEFAULT_CHART_SETTINGS,
  loadChartSettings,
  saveChartSettings,
} from "@/lib/chart-settings";

export function useChartSettings(): {
  settings: ChartSettings;
  setSettings: (next: ChartSettings) => void;
  reset: () => void;
} {
  const [settings, setSettingsState] = useState<ChartSettings>(
    DEFAULT_CHART_SETTINGS,
  );

  // Hydrate from localStorage on mount (avoids SSR mismatch).
  useEffect(() => {
    setSettingsState(loadChartSettings());
  }, []);

  const setSettings = useCallback((next: ChartSettings) => {
    setSettingsState(next);
    saveChartSettings(next);
  }, []);

  const reset = useCallback(() => {
    setSettingsState(DEFAULT_CHART_SETTINGS);
    saveChartSettings(DEFAULT_CHART_SETTINGS);
  }, []);

  return { settings, setSettings, reset };
}
