"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertFilter,
  AlertListResponse,
  listAlerts,
  markAlertRead,
  markAllAlertsRead,
} from "@/lib/alerts";

export function useAlerts(filter: AlertFilter) {
  return useQuery<AlertListResponse>({
    queryKey: ["alerts", filter],
    queryFn: () => listAlerts(filter),
    staleTime: 10_000,
  });
}

export function useMarkAlertRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => markAlertRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["alerts", "unread"] });
    },
  });
}

export function useMarkAllAlertsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => markAllAlertsRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["alerts", "unread"] });
    },
  });
}
