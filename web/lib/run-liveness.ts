export type RunUiState =
  | "running"
  | "stalled"
  | "completed"
  | "failed"
  | "cancelled";

export type TerminalState = "completed" | "failed" | "cancelled" | null;

/** Server heartbeat cadence (must match _HEARTBEAT_INTERVAL_S on the backend). */
export const HEARTBEAT_INTERVAL_MS = 8_000;

/** No signal for longer than this ⇒ treat the run as stalled / disconnected. */
export const STALL_MS = 30_000;

/**
 * Derive the user-facing run state from liveness timing + any terminal signal.
 *
 * A terminal signal (done/error/cancelled) always wins. Otherwise the run is
 * "running" while signals keep arriving, and "stalled" once none has arrived
 * for longer than STALL_MS.
 */
export function deriveRunState(args: {
  lastSignalAt: number;
  now: number;
  terminal: TerminalState;
}): RunUiState {
  const { lastSignalAt, now, terminal } = args;
  if (terminal) return terminal;
  if (now - lastSignalAt > STALL_MS) return "stalled";
  return "running";
}
