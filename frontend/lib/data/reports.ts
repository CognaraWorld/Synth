import { getBackendToken } from "@/lib/auth/session";
import { backendGet } from "@/lib/backend-client";
import {
  type BackendReportDetailResponse,
  type BackendReportListResponse,
  transformReport
} from "@/lib/transformers/reports";

export async function getReports() {
  const token = await getBackendToken();
  if (!token) {
    throw new Error("Not authenticated");
  }
  const reports = await backendGet<BackendReportListResponse>("/api/reports/?per_page=100", token);
  return reports.reports.map(transformReport);
}

export async function getReportById(reportId: string) {
  const token = await getBackendToken();
  if (!token) {
    throw new Error("Not authenticated");
  }
  return transformReport(
    await backendGet<BackendReportDetailResponse>(`/api/reports/${reportId}`, token)
  );
}
