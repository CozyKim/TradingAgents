"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Logo } from "@/components/shared/logo";
import { UnreadBell } from "@/components/alerts/unread-bell";
import { CurrencyToggle } from "@/components/nav/currency-toggle";

const TITLES: Array<[string, string]> = [
  ["/portfolio", "포트폴리오"],
  ["/run", "분석 실행"],
  ["/history", "분석 기록"],
  ["/alerts", "알림"],
  ["/schedules", "스케줄"],
  ["/settings", "설정"],
  ["/more", "더보기"],
];

function titleFor(pathname: string): string | null {
  for (const [prefix, title] of TITLES) {
    if (pathname.startsWith(prefix)) return title;
  }
  return null;
}

export function MobileTopBar() {
  const pathname = usePathname();
  const title = titleFor(pathname);

  return (
    <header
      className="md:hidden sticky top-0 z-20 flex h-14 items-center justify-between bg-bg-0/85 px-4 backdrop-blur supports-[backdrop-filter]:bg-bg-0/70"
      aria-label="Top"
    >
      <div className="flex items-center gap-2">
        {title ? (
          <Link href="/" aria-label="Home" className="flex items-center">
            <Logo collapsed />
          </Link>
        ) : (
          <Logo />
        )}
        {title && (
          <h1 className="text-[17px] font-bold tracking-[-0.02em] text-text-1">
            {title}
          </h1>
        )}
      </div>
      <div className="flex items-center gap-2">
        <CurrencyToggle compact />
        <UnreadBell />
      </div>
    </header>
  );
}
