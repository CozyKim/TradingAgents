"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  HoldingCreatePayload,
  HoldingUpdatePayload,
  createHolding,
  deleteHolding,
  listHoldings,
  updateHolding,
} from "@/lib/holdings";

export function useHoldings() {
  return useQuery({
    queryKey: ["holdings"],
    queryFn: listHoldings,
  });
}

export function useCreateHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: HoldingCreatePayload) => createHolding(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["holdings"] }),
  });
}

export function useUpdateHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: HoldingUpdatePayload }) =>
      updateHolding(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["holdings"] });
      qc.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}

export function useDeleteHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteHolding(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["holdings"] });
      qc.invalidateQueries({ queryKey: ["schedules"] });
    },
  });
}
