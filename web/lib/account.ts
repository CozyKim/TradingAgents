import { api } from "./api";

export type SessionItem = {
  id_masked: string;
  expires_at: string;
  is_current: boolean;
};

export async function listSessions(): Promise<SessionItem[]> {
  const data = await api<{ sessions: SessionItem[] }>(
    "/api/settings/account/sessions",
  );
  return data.sessions;
}

export async function changePassword(input: {
  current_password: string;
  new_password: string;
  revoke_other_sessions: boolean;
}): Promise<void> {
  await api("/api/settings/account/password", {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function revokeOtherSessions(): Promise<void> {
  await api("/api/settings/account/sessions/revoke-others", {
    method: "POST",
  });
}

export async function uploadRestore(file: File): Promise<void> {
  const fd = new FormData();
  fd.append("file", file);
  await api("/api/settings/account/restore", {
    method: "POST",
    body: fd,
  });
}

export function backupDownloadUrl(): string {
  return "/api/settings/account/backup";
}
