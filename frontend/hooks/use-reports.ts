"use client";

import { useQuery } from "@tanstack/react-query";
import { ReportDTO } from "@/types";

async function fetchReports() {
  const response = await fetch("/api/reports");
  if (!response.ok) {
    throw new Error("Failed to load reports");
  }

  const result = (await response.json()) as { data: ReportDTO[] };
  return result.data;
}

export function useReports() {
  return useQuery({
    queryKey: ["reports"],
    queryFn: fetchReports
  });
}
