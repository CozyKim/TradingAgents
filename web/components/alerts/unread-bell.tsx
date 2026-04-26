"use client";
import Link from "next/link";
import { useUnreadCount } from "@/hooks/use-unread-count";

export function UnreadBell() {
  const { data } = useUnreadCount();
  const count = data?.unread ?? 0;
  return (
    <Link
      href="/alerts"
      aria-label={`Alerts (${count} unread)`}
      className="relative inline-flex h-8 w-8 items-center justify-center rounded-md border border-border-1 bg-bg-1 text-text-2 hover:text-text-1"
    >
      <span aria-hidden>⚑</span>
      {count > 0 && (
        <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-accent text-2xs leading-4 text-white text-center font-mono">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  );
}
