"use client";
import { useEffect, useState } from "react";
import {
  useNotificationSettings,
  useTestTelegram,
  useUpdateNotificationSettings,
} from "@/hooks/use-notification-settings";

export function NotificationsForm() {
  const { data, isLoading } = useNotificationSettings();
  const update = useUpdateNotificationSettings();
  const test = useTestTelegram();

  const [token, setToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [signalChange, setSignalChange] = useState(true);
  const [runCompleted, setRunCompleted] = useState(false);
  const [runFailed, setRunFailed] = useState(true);
  const [scheduleFailed, setScheduleFailed] = useState(true);
  const [threshold, setThreshold] = useState("0.10");

  useEffect(() => {
    if (!data) return;
    setChatId(data.telegram_chat_id ?? "");
    setSignalChange(data.alert_on_signal_change);
    setRunCompleted(data.alert_on_run_completed);
    setRunFailed(data.alert_on_run_failed);
    setScheduleFailed(data.alert_on_schedule_failed);
    setThreshold(String(data.confidence_change_threshold ?? 0.1));
  }, [data]);

  if (isLoading || !data) {
    return <div className="text-text-3 text-sm">Loading…</div>;
  }

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    update.mutate({
      ...(token ? { telegram_bot_token: token } : {}),
      telegram_chat_id: chatId,
      alert_on_signal_change: signalChange,
      alert_on_run_completed: runCompleted,
      alert_on_run_failed: runFailed,
      alert_on_schedule_failed: scheduleFailed,
      confidence_change_threshold: Number(threshold),
    });
    setToken("");
  }

  return (
    <form className="space-y-6 max-w-xl" onSubmit={handleSave}>
      <fieldset className="space-y-3">
        <legend className="text-xs uppercase tracking-widest text-text-3">
          Telegram
        </legend>
        <label className="block text-xs text-text-2">
          Bot token
          <input
            type="password"
            placeholder={
              data.telegram_bot_token_set ? "•••••• (saved)" : "123:abc..."
            }
            value={token}
            onChange={(e) => setToken(e.target.value)}
            className="mt-1 w-full rounded-md border border-border-1 bg-bg-1 px-2 py-1.5 font-mono text-sm text-text-1"
          />
        </label>
        <label className="block text-xs text-text-2">
          Chat ID
          <input
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            className="mt-1 w-full rounded-md border border-border-1 bg-bg-1 px-2 py-1.5 font-mono text-sm text-text-1"
          />
        </label>
        <button
          type="button"
          onClick={() =>
            test.mutate({
              telegram_bot_token: token || undefined,
              telegram_chat_id: chatId || undefined,
            })
          }
          disabled={test.isPending}
          className="rounded-md border border-border-1 px-3 py-1.5 text-xs text-text-2 hover:text-text-1 disabled:opacity-40"
        >
          {test.isPending ? "Testing…" : "Send test message"}
        </button>
        {test.data && (
          <div className={test.data.ok ? "text-pos text-xs" : "text-neg text-xs"}>
            {test.data.ok
              ? `OK — bot @${test.data.bot_username ?? "?"}`
              : `Failed: ${test.data.error}`}
          </div>
        )}
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-xs uppercase tracking-widest text-text-3">
          Triggers
        </legend>
        <ToggleRow
          label="Signal changes (BUY⇄SELL⇄HOLD)"
          checked={signalChange}
          onChange={setSignalChange}
        />
        <ToggleRow
          label="Every completed run"
          checked={runCompleted}
          onChange={setRunCompleted}
        />
        <ToggleRow
          label="Failed runs"
          checked={runFailed}
          onChange={setRunFailed}
        />
        <ToggleRow
          label="Failed schedules"
          checked={scheduleFailed}
          onChange={setScheduleFailed}
        />
        <label className="block text-xs text-text-2 mt-2">
          Confidence change threshold (0–1, blank disables)
          <input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            className="mt-1 w-32 rounded-md border border-border-1 bg-bg-1 px-2 py-1.5 font-mono text-sm text-text-1"
          />
        </label>
      </fieldset>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={update.isPending}
          className="rounded-md bg-accent px-4 py-1.5 text-sm text-white hover:bg-accent/90 disabled:opacity-40"
        >
          {update.isPending ? "Saving…" : "Save"}
        </button>
        {update.isSuccess && <span className="text-pos text-xs">Saved.</span>}
      </div>
    </form>
  );
}

function ToggleRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-text-2">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  );
}
