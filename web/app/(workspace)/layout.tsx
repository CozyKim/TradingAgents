import { UnreadBell } from "@/components/alerts/unread-bell";
import { Sidebar } from "@/components/nav/sidebar";
import { TabBar } from "@/components/nav/tab-bar";
import { MobileTopBar } from "@/components/nav/mobile-top-bar";
import { RunningRunsIndicator } from "@/components/run/running-runs-indicator";
import { CurrencyProvider } from "@/lib/currency";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <CurrencyProvider>
      <div className="flex min-h-screen bg-bg-0">
        <Sidebar />
        <main className="flex-1 flex flex-col pb-[calc(72px+env(safe-area-inset-bottom))] md:pb-0">
          <MobileTopBar />
          <header className="hidden md:flex sticky top-0 z-20 items-center justify-end gap-2 px-8 py-3 bg-bg-0/80 backdrop-blur supports-[backdrop-filter]:bg-bg-0/70">
            <RunningRunsIndicator />
            <UnreadBell />
          </header>
          <div className="flex-1">{children}</div>
        </main>
        <TabBar />
      </div>
    </CurrencyProvider>
  );
}
