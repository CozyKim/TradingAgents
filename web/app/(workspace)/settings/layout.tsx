import Link from "next/link";

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col md:flex-row gap-6">
      <aside className="md:w-48 shrink-0">
        <ul className="flex md:flex-col gap-1 text-sm">
          <li>
            <Link
              href="/settings/notifications"
              className="block rounded-md px-2 py-1.5 text-text-2 hover:bg-bg-2 hover:text-text-1"
            >
              Notifications
            </Link>
          </li>
          <li>
            <Link
              href="/settings/account"
              className="block rounded-md px-2 py-1.5 text-text-2 hover:bg-bg-2 hover:text-text-1"
            >
              Account
            </Link>
          </li>
        </ul>
      </aside>
      <section className="flex-1 min-w-0">{children}</section>
    </div>
  );
}
