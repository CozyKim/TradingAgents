import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  return (
    <div className="px-4 md:px-6 py-6 md:py-8 max-w-screen-xl mx-auto">
      <h1 className="text-xl font-bold text-text-1 mb-1">Dashboard</h1>
      <p className="text-xs text-text-3 mb-6">Personal workbench</p>
      <Card>
        <CardHeader>
          <CardTitle>Welcome</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-text-2">
            M1 foundation is up. Run analysis, history, portfolio, and more arrive in M2+.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
