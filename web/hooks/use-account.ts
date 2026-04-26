"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  changePassword,
  listSessions,
  revokeOtherSessions,
  uploadRestore,
} from "@/lib/account";

export function useSessions() {
  return useQuery({
    queryKey: ["account", "sessions"],
    queryFn: listSessions,
    staleTime: 5_000,
  });
}

export function useChangePassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: changePassword,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["account"] }),
  });
}

export function useRevokeOtherSessions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: revokeOtherSessions,
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["account", "sessions"] }),
  });
}

export function useRestore() {
  return useMutation({ mutationFn: uploadRestore });
}
