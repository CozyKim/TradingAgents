"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSchedules } from "@/hooks/use-schedules";
import { SchedulesTable } from "@/components/schedules/schedules-table";

export default function SchedulesPage() {
  const { data, isLoading, error } = useSchedules();
  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-1 mb-1">Schedules</h1>
          <p className="text-xs text-text-3">
            Cron-driven auto analyses. Holdings with monitor on appear here too.
          </p>
        </div>
        <Link href="/schedules/new">
          <Button>+ New schedule</Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All schedules</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-text-3">Loading…</p>
          ) : error ? (
            <p className="text-sm text-neg">{(error as Error).message}</p>
          ) : (
            <SchedulesTable rows={data?.items ?? []} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
