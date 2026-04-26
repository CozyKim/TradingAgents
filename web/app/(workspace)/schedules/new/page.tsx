import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScheduleForm } from "@/components/schedules/schedule-form";

export default function NewSchedulePage() {
  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-1 mb-1">New schedule</h1>
        <p className="text-xs text-text-3">
          Pick tickers, a cron expression, and analysis preset.{" "}
          <Link className="underline" href="/schedules">
            Back to list
          </Link>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <ScheduleForm />
        </CardContent>
      </Card>
    </div>
  );
}
