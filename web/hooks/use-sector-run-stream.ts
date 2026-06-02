"use client";
import { useEffect, useReducer, useRef } from "react";

import {
  deriveRunState,
  type RunUiState,
  type TerminalState,
} from "@/lib/run-liveness";
import { openSectorRunStream } from "@/lib/sectors";

export interface SectorRunStream {
  phase: string | null;
  state: RunUiState;
  elapsedMs: number;
  lastSignalAgoMs: number;
  error: string | null;
}

interface InternalState {
  phase: string | null;
  terminal: TerminalState;
  error: string | null;
  startedAt: number;
  lastSignalAt: number;
  now: number;
}

type Action =
  | { kind: "reset"; t: number }
  | { kind: "signal"; t: number }
  | { kind: "phase"; phase: string | null; t: number }
  | { kind: "terminal"; terminal: TerminalState; error: string | null; t: number }
  | { kind: "tick"; t: number };

function reducer(s: InternalState, a: Action): InternalState {
  switch (a.kind) {
    case "reset":
      return {
        phase: null, terminal: null, error: null,
        startedAt: a.t, lastSignalAt: a.t, now: a.t,
      };
    case "signal":
      return { ...s, lastSignalAt: a.t, now: a.t };
    case "phase":
      return { ...s, phase: a.phase ?? s.phase, lastSignalAt: a.t, now: a.t };
    case "terminal":
      return { ...s, terminal: a.terminal, error: a.error ?? s.error, now: a.t };
    case "tick":
      return { ...s, now: a.t };
  }
}

const INIT: InternalState = {
  phase: null, terminal: null, error: null,
  startedAt: 0, lastSignalAt: 0, now: 0,
};

/**
 * Subscribe to a sector run's SSE stream and derive a clear liveness state.
 *
 * Returns one of running/stalled/completed/failed/cancelled plus elapsed and
 * last-signal timings. A 1s tick re-evaluates the stall timer until a terminal
 * event arrives.
 */
export function useSectorRunStream(
  sectorId: number | undefined,
  runId: string | undefined,
  enabled: boolean,
): SectorRunStream {
  const [s, dispatch] = useReducer(reducer, INIT);
  const terminalRef = useRef<TerminalState>(null);

  useEffect(() => {
    if (!enabled || sectorId == null || !runId) return;
    terminalRef.current = null;
    dispatch({ kind: "reset", t: Date.now() });
    const close = openSectorRunStream(sectorId, runId, {
      onProgress: (phase) => dispatch({ kind: "phase", phase, t: Date.now() }),
      onHeartbeat: () => dispatch({ kind: "signal", t: Date.now() }),
      onDone: () => {
        terminalRef.current = "completed";
        dispatch({ kind: "terminal", terminal: "completed", error: null, t: Date.now() });
      },
      onCancelled: () => {
        terminalRef.current = "cancelled";
        dispatch({ kind: "terminal", terminal: "cancelled", error: null, t: Date.now() });
      },
      onError: (message) => {
        terminalRef.current = "failed";
        dispatch({ kind: "terminal", terminal: "failed", error: message, t: Date.now() });
      },
    });
    const tick = setInterval(() => {
      if (terminalRef.current) return;
      dispatch({ kind: "tick", t: Date.now() });
    }, 1_000);
    return () => {
      clearInterval(tick);
      close();
    };
  }, [enabled, sectorId, runId]);

  const state = deriveRunState({
    lastSignalAt: s.lastSignalAt,
    now: s.now,
    terminal: s.terminal,
  });
  return {
    phase: s.phase,
    state,
    elapsedMs: Math.max(0, s.now - s.startedAt),
    lastSignalAgoMs: Math.max(0, s.now - s.lastSignalAt),
    error: s.error,
  };
}
