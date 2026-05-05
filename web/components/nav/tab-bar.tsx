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
  { href: "/", label: "홈", icon: Home },
  { href: "/portfolio", label: "포트폴리오", icon: Briefcase },
  { href: "/run", label: "분석", icon: Plus },
  { href: "/alerts", label: "알림", icon: Flag },
  { href: "/more", label: "더보기", icon: Menu },
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
      className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-bg-1/95 backdrop-blur shadow-nav supports-[backdrop-filter]:bg-bg-1/85 pb-[env(safe-area-inset-bottom)]"
      aria-label="Primary"
    >
      <ul className="grid grid-cols-5 px-2 pt-2 pb-1.5">
        {TABS.map((tab, i) => {
          const isFab = i === 2;
          const active =
            tab.href === "/"
              ? pathname === "/"
              : pathname.startsWith(tab.href);
          const Icon = tab.icon;

          if (isFab) {
            return (
              <li key={tab.href} className="flex justify-center">
                <Link
                  href={tab.href}
                  className="relative -mt-7 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent text-white shadow-pop ring-4 ring-bg-1 transition-transform active:scale-95 hover:bg-[#1B64DA]"
                  aria-label={tab.label}
                >
                  <Icon className="h-6 w-6" aria-hidden strokeWidth={2.6} />
                  {runningCount > 0 && (
                    <span className="absolute -right-1 -top-1 inline-flex min-w-[20px] items-center justify-center rounded-full bg-signal-buy px-1.5 text-[10px] font-bold leading-[18px] text-white ring-2 ring-bg-1">
                      {runningCount > 9 ? "9+" : runningCount}
                    </span>
                  )}
                </Link>
              </li>
            );
          }
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-xl py-1.5 text-[10.5px] font-semibold tracking-[-0.01em] transition-colors",
                  active ? "text-text-1" : "text-text-3",
                )}
              >
                <Icon
                  className="h-[22px] w-[22px]"
                  strokeWidth={active ? 2.6 : 2}
                  aria-hidden
                />
                <span>{tab.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
