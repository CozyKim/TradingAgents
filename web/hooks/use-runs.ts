"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelRun,
  createRun,
  CreateRunPayload,
  Decision,
  getRun,
  listRuns,
  RunStatus,
} from "@/lib/runs";

export function useRunList(
  params: {
    ticker?: string;
    status?: RunStatus;
    decision?: Decision;
    page?: number;
    page_size?: number;
  },
  options: {
    refetchInterval?: number | false;
    staleTime?: number;
  } = {},
) {
  return useQuery({
    queryKey: ["runs", params],
    queryFn: () => listRuns(params),
    refetchInterval: options.refetchInterval,
    staleTime: options.staleTime,
  });
}

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => getRun(runId!),
    enabled: !!runId,
    refetchInterval: (q) => {
      const data = q.state.data as { status?: string } | undefined;
      return data?.status === "running" ? 5000 : false;
    },
  });
}

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateRunPayload) => createRun(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export function useCancelRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => cancelRun(runId),
    onSuccess: (_d, runId) => {
      qc.invalidateQueries({ queryKey: ["run", runId] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}
