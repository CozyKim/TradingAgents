import { NotificationsForm } from "@/components/settings/notifications-form";

export default function SettingsNotificationsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-lg text-text-1">Notifications</h1>
      <p className="text-sm text-text-2">
        In-app alerts are always recorded. Configure Telegram to also receive
        push notifications.
      </p>
      <NotificationsForm />
    </div>
  );
}
