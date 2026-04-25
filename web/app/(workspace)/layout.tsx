import { Sidebar } from "@/components/nav/sidebar";
import { TabBar } from "@/components/nav/tab-bar";

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-bg-0">
      <Sidebar />
      <main className="flex-1 pb-20 md:pb-0">{children}</main>
      <TabBar />
    </div>
  );
}
