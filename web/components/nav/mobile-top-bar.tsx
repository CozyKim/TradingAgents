"use client";
import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search } from "lucide-react";

import { Logo } from "@/components/shared/logo";
import { CurrencyToggle } from "@/components/nav/currency-toggle";
import { TickerSearchOverlay } from "@/components/nav/ticker-search-overlay";

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
  const [searchOpen, setSearchOpen] = useState(false);
  const searchButtonRef = useRef<HTMLButtonElement>(null);

  // 더미 히스토리 엔트리를 쌓아 안드로이드 뒤로가기가 오버레이를 닫게 한다.
  // effect가 아니라 핸들러에서 호출해야 StrictMode 이중 실행에 걸리지 않는다.
  const openSearch = useCallback(() => {
    window.history.pushState({ tickerSearchOpen: true }, "");
    setSearchOpen(true);
  }, []);

  const closeSearch = useCallback(() => setSearchOpen(false), []);

  return (
    <>
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
          <button
            ref={searchButtonRef}
            type="button"
            aria-label="티커 검색"
            onClick={openSearch}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-border-1 bg-bg-1 text-text-2 hover:text-text-1"
          >
            <Search className="h-4 w-4" aria-hidden />
          </button>
          <CurrencyToggle compact />
        </div>
      </header>
      <TickerSearchOverlay
        open={searchOpen}
        onClose={closeSearch}
        restoreFocusRef={searchButtonRef}
      />
    </>
  );
}
