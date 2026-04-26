"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  Briefcase,
  Plus,
  Flag,
  Menu,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useRunList } from "@/hooks/use-runs";

type Tab = { href: string; label: string; icon: LucideIcon };

const TABS: Tab[] = [
  { href: "/", label: "Home", icon: Home },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/run", label: "Run", icon: Plus },
  { href: "/alerts", label: "Alerts", icon: Flag },
  { href: "/more", label: "More", icon: Menu },
];

export function TabBar() {
  const pathname = usePathname();
  const { data } = useRunList(
    { status: "running", page_size: 1 },
    { refetchInterval: 5000, staleTime: 0 },
  );
  const runningCount = data?.total ?? 0;
  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 z-30 grid grid-cols-5 border-t border-border-1 bg-bg-1 pb-[env(safe-area-inset-bottom)]"
      aria-label="Primary"
    >
      {TABS.map((tab, i) => {
        const isFab = i === 2;
        const active =
          tab.href === "/"
            ? pathname === "/"
            : pathname.startsWith(tab.href);
        const Icon = tab.icon;

        if (isFab) {
          return (
            <div key={tab.href} className="flex justify-center -mt-5">
              <Link
                href={tab.href}
                className="relative flex h-12 w-12 items-center justify-center rounded-full bg-accent text-white shadow-lg shadow-accent/30 hover:bg-accent/90"
                aria-label={tab.label}
              >
                <Icon className="h-5 w-5" aria-hidden />
                {runningCount > 0 && (
                  <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-signal-buy px-1 text-center text-2xs font-semibold leading-5 text-white">
                    {runningCount > 9 ? "9+" : runningCount}
                  </span>
                )}
              </Link>
            </div>
          );
        }
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "flex flex-col items-center gap-0.5 py-2 text-2xs",
              active ? "text-accent" : "text-text-3",
            )}
          >
            <Icon className="h-4 w-4" aria-hidden />
            <span>{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
