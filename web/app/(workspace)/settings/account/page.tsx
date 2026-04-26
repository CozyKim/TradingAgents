import { AccountBackupButton } from "@/components/settings/account-backup-button";
import { AccountPasswordForm } from "@/components/settings/account-password-form";
import { AccountRestoreForm } from "@/components/settings/account-restore-form";
import { AccountSessionsList } from "@/components/settings/account-sessions-list";

export default function SettingsAccountPage() {
  return (
    <div className="space-y-8">
      <section className="space-y-2">
        <h1 className="text-lg text-text-1">Account</h1>
        <p className="text-sm text-text-2">
          Manage your password, active sessions, and data backups.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-xs uppercase tracking-widest text-text-3">Password</h2>
        <AccountPasswordForm />
      </section>

      <section className="space-y-3">
        <h2 className="text-xs uppercase tracking-widest text-text-3">Sessions</h2>
        <AccountSessionsList />
      </section>

      <section className="space-y-3">
        <h2 className="text-xs uppercase tracking-widest text-text-3">Backup</h2>
        <p className="text-xs text-text-3">
          Downloads the entire SQLite file (analyses, holdings, schedules, alerts, settings).
        </p>
        <AccountBackupButton />
      </section>

      <section className="space-y-3">
        <h2 className="text-xs uppercase tracking-widest text-text-3">Restore</h2>
        <p className="text-xs text-signal-sell">
          Warning: replaces ALL current data and signs you out from every device.
        </p>
        <AccountRestoreForm />
      </section>
    </div>
  );
}
