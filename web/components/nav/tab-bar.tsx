"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

type Tab = { href: string; label: string; icon: string };

const TABS: Tab[] = [
  { href: "/", label: "Home", icon: "▦" },
  { href: "/portfolio", label: "Portfolio", icon: "◈" },
  { href: "/run", label: "Run", icon: "+" },
  { href: "/alerts", label: "Alerts", icon: "⚑" },
  { href: "/more", label: "More", icon: "≡" },
];

export function TabBar() {
  const pathname = usePathname();
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

        if (isFab) {
          return (
            <div key={tab.href} className="flex justify-center -mt-5">
              <Link
                href={tab.href}
                className="flex h-12 w-12 items-center justify-center rounded-full bg-accent text-white shadow-lg shadow-accent/30 hover:bg-accent/90"
                aria-label={tab.label}
              >
                <span className="text-lg leading-none">{tab.icon}</span>
              </Link>
            </div>
          );
        }
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={cn(
              "flex flex-col items-center gap-0.5 py-2 text-[10px]",
              active ? "text-accent" : "text-text-3",
            )}
          >
            <span className="text-base leading-none" aria-hidden>{tab.icon}</span>
            <span>{tab.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
