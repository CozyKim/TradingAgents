import { UnreadBell } from "@/components/alerts/unread-bell";
import { Sidebar } from "@/components/nav/sidebar";
import { TabBar } from "@/components/nav/tab-bar";
import { RunningRunsIndicator } from "@/components/run/running-runs-indicator";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-bg-0">
      <Sidebar />
      <main className="flex-1 pb-20 md:pb-0 flex flex-col">
        <header className="hidden md:flex items-center justify-end gap-2 px-6 py-2 border-b border-border-1 bg-bg-0">
          <RunningRunsIndicator />
          <UnreadBell />
        </header>
        <div className="flex-1">{children}</div>
      </main>
      <TabBar />
    </div>
  );
}
