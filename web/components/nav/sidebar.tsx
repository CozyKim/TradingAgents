"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Play,
  History,
  Briefcase,
  Clock,
  Flag,
  Bell,
  UserCircle2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/shared/logo";

type NavItem = { href: string; label: string; icon: LucideIcon };

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "Workspace",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/run", label: "Run Analysis", icon: Play },
      { href: "/history", label: "History", icon: History },
    ],
  },
  {
    title: "Tracking",
    items: [
      { href: "/portfolio", label: "Portfolio", icon: Briefcase },
      { href: "/schedules", label: "Schedules", icon: Clock },
      { href: "/alerts", label: "Alerts", icon: Flag },
    ],
  },
  {
    title: "System",
    items: [
      { href: "/settings/notifications", label: "Notifications", icon: Bell },
      { href: "/settings/account", label: "Account", icon: UserCircle2 },
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
            <div className="px-2 pb-1 text-2xs uppercase tracking-widest text-text-3">
              {section.title}
            </div>
            <ul className="flex flex-col gap-0.5">
              {section.items.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                const Icon = item.icon;
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
                      <Icon className="h-3.5 w-3.5" aria-hidden />
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
