import { RunForm } from "@/components/run/run-form";

export default function RunPage() {
  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-md mx-auto">
      <h1 className="text-xl font-bold text-text-1 mb-1">Run Analysis</h1>
      <p className="text-xs text-text-3 mb-6">Pick a ticker and analyst mix</p>
      <RunForm />
    </div>
  );
}
