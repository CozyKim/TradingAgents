"use client";
import { useEffect, useReducer, useRef } from "react";
import { openRunStream } from "@/lib/sse";

export interface AgentMessage {
  role: string;
  text: string;
  seq: number;
}

export interface RunStreamState {
  messages: AgentMessage[];
  step: number;
  total: number;
  phase: string | null;
  phaseLabel: string | null;
  done: boolean;
  decision: string | null;
  confidence: number | null;
  error: string | null;
  cancelled: boolean;
}

const init: RunStreamState = {
  messages: [],
  step: 0,
  total: 0,
  phase: null,
  phaseLabel: null,
  done: false,
  decision: null,
  confidence: null,
  error: null,
  cancelled: false,
};

type Action =
  | { kind: "reset" }
  | { kind: "msg"; payload: AgentMessage }
  | {
      kind: "progress";
      step: number;
      total: number;
      phase: string | null;
      phaseLabel: string | null;
    }
  | { kind: "done"; decision: string | null; confidence: number | null }
  | { kind: "error"; message: string }
  | { kind: "cancelled" };

function reducer(s: RunStreamState, a: Action): RunStreamState {
  switch (a.kind) {
    case "reset":
      return init;
    case "msg":
      return { ...s, messages: [...s.messages, a.payload] };
    case "progress":
      return {
        ...s,
        step: a.step,
        total: a.total || s.total,
        phase: a.phase ?? s.phase,
        phaseLabel: a.phaseLabel ?? s.phaseLabel,
      };
    case "done":
      return { ...s, done: true, decision: a.decision, confidence: a.confidence };
    case "error":
      return { ...s, error: a.message, done: true };
    case "cancelled":
      return { ...s, cancelled: true, done: true };
  }
}

export function useRunStream(runId: string | undefined): RunStreamState {
  const [state, dispatch] = useReducer(reducer, init);
  const seqRef = useRef(0);

  useEffect(() => {
    if (!runId) return;
    dispatch({ kind: "reset" });
    seqRef.current = 0;
    const close = openRunStream(runId, {
      onEvent: (type, data, raw) => {
        const seq = Number(raw.lastEventId || ++seqRef.current);
        if (type === "agent_message") {
          const d = data as { role?: string; text?: string };
          dispatch({
            kind: "msg",
            payload: { role: d.role ?? "agent", text: d.text ?? "", seq },
          });
        } else if (type === "progress") {
          const d = data as {
            step?: number;
            total?: number;
            phase?: string;
            phase_label?: string;
          };
          dispatch({
            kind: "progress",
            step: d.step ?? 0,
            total: d.total ?? 0,
            phase: d.phase ?? null,
            phaseLabel: d.phase_label ?? null,
          });
        } else if (type === "done") {
          const d = data as { decision?: string | null; confidence?: number | null };
          dispatch({
            kind: "done",
            decision: d.decision ?? null,
            confidence: d.confidence ?? null,
          });
        } else if (type === "error") {
          const d = data as { message?: string };
          dispatch({ kind: "error", message: d.message ?? "Unknown error" });
        } else if (type === "cancelled") {
          dispatch({ kind: "cancelled" });
        }
      },
    });
    return () => close();
  }, [runId]);

  return state;
}
