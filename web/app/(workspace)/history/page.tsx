"use client";
import { useState } from "react";

import { HistoryFilters, FilterState } from "@/components/history/history-filters";
import { HistoryTable } from "@/components/history/history-table";
import { Button } from "@/components/ui/button";
import { useRunList } from "@/hooks/use-runs";

export default function HistoryPage() {
  const [filters, setFilters] = useState<FilterState>({});
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const q = useRunList({ ...filters, page, page_size: pageSize });

  const total = q.data?.total ?? 0;
  const lastPage = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <h1 className="text-xl font-bold text-text-1 mb-1">History</h1>
      <p className="text-xs text-text-3 mb-6">{total} analyses stored</p>

      <HistoryFilters
        value={filters}
        onChange={(f) => {
          setFilters(f);
          setPage(1);
        }}
      />

      {q.isLoading ? (
        <p className="text-xs text-text-3">Loading…</p>
      ) : (
        <HistoryTable rows={q.data?.items ?? []} />
      )}

      {total > pageSize && (
        <div className="flex items-center justify-end gap-2 mt-4">
          <Button
            variant="outline"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Prev
          </Button>
          <span className="text-xs text-text-3 font-num">
            {page} / {lastPage}
          </span>
          <Button
            variant="outline"
            disabled={page >= lastPage}
            onClick={() => setPage((p) => Math.min(lastPage, p + 1))}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
