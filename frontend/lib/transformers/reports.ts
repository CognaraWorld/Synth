import type { ReportDTO } from "@/types";
import { mapPlatformDisplay } from "@/lib/transformers/meetings";

export interface BackendReportListItemResponse {
  id: string;
  meeting_id: string;
  platform: string;
  meeting_link: string;
  started_at?: string | null;
  ended_at?: string | null;
  duration_minutes?: number | null;
  content_preview: string;
  action_items: string[];
  email_delivery_status: string;
  email_delivered_at?: string | null;
  has_pdf: boolean;
  has_docx: boolean;
  created_at: string;
}

export interface BackendReportListResponse {
  reports: BackendReportListItemResponse[];
  total: number;
  page: number;
  per_page: number;
}

export interface BackendReportDetailResponse {
  id: string;
  meeting_id: string;
  platform: string;
  meeting_link: string;
  started_at?: string | null;
  ended_at?: string | null;
  duration_minutes?: number | null;
  content: string;
  key_points: string[];
  action_items: string[];
  decisions: string[];
  email_delivery_status: string;
  email_delivered_at?: string | null;
  has_pdf: boolean;
  has_docx: boolean;
  pdf_download_path?: string | null;
  docx_download_path?: string | null;
  created_at: string;
}

export function transformReport(
  backend: BackendReportListItemResponse | BackendReportDetailResponse
): ReportDTO {
  const platform = mapPlatformDisplay(backend.platform);

  return {
    id: String(backend.id),
    meetingId: String(backend.meeting_id),
    meetingTitle: `${platform} meeting`,
    scheduledTime: backend.started_at ?? backend.created_at,
    durationMinutes: Math.round(backend.duration_minutes ?? 0),
    summary: "content" in backend ? backend.content : backend.content_preview ?? "",
    actionItems: (backend.action_items ?? []).map((text, index) => ({
      id: `ai_${backend.id}_${index}`,
      label: text,
      done: false
    })),
    pdfUrl: backend.has_pdf ? `/api/reports/${backend.id}/download/pdf` : "",
    wordUrl: backend.has_docx ? `/api/reports/${backend.id}/download/docx` : ""
  };
}
