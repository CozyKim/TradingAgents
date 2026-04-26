"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ScheduleCreatePayload,
  ScheduleUpdatePayload,
  createSchedule,
  deleteSchedule,
  listSchedules,
  runScheduleNow,
  updateSchedule,
} from "@/lib/schedules";

export function useSchedules() {
  return useQuery({
    queryKey: ["schedules"],
    queryFn: listSchedules,
  });
}

export function useCreateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: ScheduleCreatePayload) => createSchedule(p),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useUpdateSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ScheduleUpdatePayload }) =>
      updateSchedule(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useDeleteSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteSchedule(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }),
  });
}

export function useRunScheduleNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => runScheduleNow(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["schedules"] });
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}
