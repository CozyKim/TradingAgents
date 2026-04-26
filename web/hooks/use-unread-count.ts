"use client";
import { useQuery } from "@tanstack/react-query";
import { fetchUnreadCount } from "@/lib/alerts";

export function useUnreadCount() {
  return useQuery({
    queryKey: ["alerts", "unread"],
    queryFn: fetchUnreadCount,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}
