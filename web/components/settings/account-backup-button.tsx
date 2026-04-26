"use client";
import { Button } from "@/components/ui/button";
import { backupDownloadUrl } from "@/lib/account";

export function AccountBackupButton() {
  return (
    <a href={backupDownloadUrl()} download>
      <Button variant="outline">Download backup (.db)</Button>
    </a>
  );
}
