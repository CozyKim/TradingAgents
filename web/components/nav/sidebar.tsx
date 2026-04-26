"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/shared/logo";

type NavItem = { href: string; label: string; icon: string };

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "Workspace",
    items: [
      { href: "/", label: "Dashboard", icon: "▦" },
      { href: "/run", label: "Run Analysis", icon: "▶" },
      { href: "/history", label: "History", icon: "▤" },
    ],
  },
  {
    title: "Tracking",
    items: [
      { href: "/portfolio", label: "Portfolio", icon: "◈" },
      { href: "/schedules", label: "Schedules", icon: "◷" },
      { href: "/alerts", label: "Alerts", icon: "⚑" },
    ],
  },
  {
    title: "System",
    items: [
      { href: "/settings/notifications", label: "Notifications", icon: "⚙" },
      { href: "/settings/account", label: "Account", icon: "◉" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex md:w-[180px] flex-col border-r border-border-1 bg-bg-1 py-4 px-2">
      <div className="pb-4 border-b border-border-1 mb-3">
        <Logo />
      </div>
      <nav className="flex flex-col gap-3">
        {SECTIONS.map((section) => (
          <div key={section.title}>
            <div className="px-2 pb-1 text-[10px] uppercase tracking-widest text-text-3">
              {section.title}
            </div>
            <ul className="flex flex-col gap-0.5">
              {section.items.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "flex items-center gap-2 rounded-md px-2 py-1.5 text-xs",
                        active
                          ? "bg-bg-2 text-text-1"
                          : "text-text-2 hover:bg-bg-2 hover:text-text-1",
                      )}
                    >
                      <span aria-hidden>{item.icon}</span>
                      <span>{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
