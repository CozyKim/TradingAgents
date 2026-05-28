"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Play,
  History,
  Layers,
  Briefcase,
  Clock,
  Flag,
  Bell,
  UserCircle2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/shared/logo";
import { CurrencyToggle } from "@/components/nav/currency-toggle";

type NavItem = { href: string; label: string; icon: LucideIcon };

const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "워크스페이스",
    items: [
      { href: "/", label: "대시보드", icon: LayoutDashboard },
      { href: "/run", label: "분석 실행", icon: Play },
      { href: "/history", label: "분석 기록", icon: History },
      { href: "/sectors", label: "산업·섹터", icon: Layers },
    ],
  },
  {
    title: "트래킹",
    items: [
      { href: "/portfolio", label: "포트폴리오", icon: Briefcase },
      { href: "/schedules", label: "스케줄", icon: Clock },
      { href: "/alerts", label: "알림", icon: Flag },
    ],
  },
  {
    title: "시스템",
    items: [
      { href: "/settings/notifications", label: "알림 설정", icon: Bell },
      { href: "/settings/account", label: "계정", icon: UserCircle2 },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex md:w-[232px] flex-col bg-bg-0 px-3 pt-5 pb-4">
      <div className="px-2 pb-5">
        <Logo />
      </div>
      <nav className="flex flex-col gap-5">
        {SECTIONS.map((section) => (
          <div key={section.title}>
            <div className="px-3 pb-1.5 text-[11px] font-semibold tracking-[-0.01em] text-text-3">
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
                        "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-[14px] font-semibold tracking-[-0.01em] transition-colors",
                        active
                          ? "bg-accent-muted text-accent"
                          : "text-text-2 hover:bg-bg-1 hover:text-text-1",
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-[18px] w-[18px]",
                          active ? "text-accent" : "text-text-3",
                        )}
                        aria-hidden
                        strokeWidth={active ? 2.4 : 2}
                      />
                      <span>{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
      <div className="mt-auto px-3 pt-4">
        <div className="text-[11px] font-semibold tracking-[-0.01em] text-text-3 pb-1.5">
          표시 통화
        </div>
        <CurrencyToggle />
      </div>
    </aside>
  );
}
