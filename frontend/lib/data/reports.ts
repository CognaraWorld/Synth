import { getBackendToken } from "@/lib/auth/session";
import { BackendError, backendGet } from "@/lib/backend-client";
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
  try {
    return transformReport(
      await backendGet<BackendReportDetailResponse>(`/api/reports/${reportId}`, token)
    );
  } catch (err) {
    if (err instanceof BackendError && err.status === 404) {
      return null;
    }
    throw err;
  }
}
