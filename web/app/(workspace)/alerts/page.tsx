"use client";
import { useState } from "react";
import { AlertsFilterBar } from "@/components/alerts/alerts-filter-bar";
import { AlertRow } from "@/components/alerts/alert-row";
import {
  useAlerts,
  useMarkAlertRead,
  useMarkAllAlertsRead,
} from "@/hooks/use-alerts";
import type { AlertFilter, AlertType } from "@/lib/alerts";

export default function AlertsPage() {
  const [type, setType] = useState<AlertType | "all">("all");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);

  const filter: AlertFilter = {
    page,
    page_size: 20,
    ...(type !== "all" ? { type } : {}),
    ...(unreadOnly ? { read: false } : {}),
  };
  const { data, isLoading } = useAlerts(filter);
  const markRead = useMarkAlertRead();
  const markAll = useMarkAllAlertsRead();

  return (
    <div className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-lg text-text-1">Alerts</h1>
        <button
          onClick={() => markAll.mutate()}
          disabled={markAll.isPending || (data?.total ?? 0) === 0}
          className="text-xs text-text-2 hover:text-text-1 disabled:opacity-40"
        >
          Mark all read
        </button>
      </header>
      <AlertsFilterBar
        type={type}
        unreadOnly={unreadOnly}
        onChangeType={(t) => {
          setType(t);
          setPage(1);
        }}
        onToggleUnread={(v) => {
          setUnreadOnly(v);
          setPage(1);
        }}
      />
      {isLoading ? (
        <div className="text-text-3 text-sm">Loading…</div>
      ) : data && data.items.length > 0 ? (
        <ul className="space-y-2">
          {data.items.map((a) => (
            <AlertRow
              key={a.id}
              alert={a}
              onMarkRead={(id) => markRead.mutate(id)}
            />
          ))}
        </ul>
      ) : (
        <div className="text-text-3 text-sm">No alerts.</div>
      )}
      {data && data.total > data.page_size && (
        <div className="flex items-center gap-2 text-xs text-text-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded-md border border-border-1 px-2 py-1 disabled:opacity-40"
          >
            Prev
          </button>
          <span>
            Page {data.page} of {Math.ceil(data.total / data.page_size)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page * data.page_size >= data.total}
            className="rounded-md border border-border-1 px-2 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
