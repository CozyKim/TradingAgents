"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const ITEMS = [
  { href: "/history", label: "History", desc: "Past analyses" },
  { href: "/schedules", label: "Schedules", desc: "Recurring runs" },
  { href: "/settings/notifications", label: "Notifications", desc: "Alerts + Telegram" },
  { href: "/settings/account", label: "Account", desc: "Password, sessions, backup" },
];

export default function MorePage() {
  const router = useRouter();
  return (
    <div className="px-4 py-6 max-w-screen-md mx-auto space-y-3">
      <h1 className="text-2xl font-bold text-text-1">More</h1>
      <ul className="grid gap-2">
        {ITEMS.map((it) => (
          <li key={it.href}>
            <Link
              href={it.href}
              className="block border border-border-1 rounded-md bg-bg-1 px-4 py-3 hover:bg-bg-2"
            >
              <div className="text-sm text-text-1">{it.label}</div>
              <div className="text-xs text-text-3">{it.desc}</div>
            </Link>
          </li>
        ))}
      </ul>
      <Button
        variant="outline"
        className="w-full mt-4"
        onClick={async () => {
          try {
            await api("/api/auth/logout", { method: "POST" });
          } catch {
            // Ignore — we still navigate to /login.
          }
          router.push("/login");
        }}
      >
        Log out
      </Button>
    </div>
  );
}
