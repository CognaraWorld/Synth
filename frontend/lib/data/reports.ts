import { getBackendToken } from "@/lib/auth/session";
import { backendGet } from "@/lib/backend-client";
import { sampleReports } from "@/lib/sample-data";
import {
  type BackendReportDetailResponse,
  type BackendReportListResponse,
  transformReport
} from "@/lib/transformers/reports";

export async function getReports() {
  const token = await getBackendToken();
  if (!token) return sampleReports;

  try {
    const reports = await backendGet<BackendReportListResponse>("/api/reports/?per_page=100", token);
    return reports.reports.map(transformReport);
  } catch (err) {
    console.error("[reports] getReports failed:", err);
    return sampleReports;
  }
}

export async function getReportById(reportId: string) {
  const token = await getBackendToken();
  if (!token) return sampleReports[0];

  try {
    const report = await backendGet<BackendReportDetailResponse>(`/api/reports/${reportId}`, token);
    return transformReport(report);
  } catch (err) {
    console.error("[reports] getReportById failed:", err);
    return sampleReports[0];
  }
}
