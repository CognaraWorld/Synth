import type { DashboardStatsDTO, UsageRecordDTO } from "@/types";
import { mapPlatformDisplay } from "@/lib/transformers/meetings";

export interface BackendUsageSummaryResponse {
  year: number;
  month: number;
  meeting_count: number;
  total_minutes: number;
  average_minutes: number;
}

export interface BackendCreditBalanceResponse {
  credits: number;
  user_id: string;
}

export interface BackendUsageRecordResponse {
  id: string;
  meeting_id: string;
  platform: string;
  meeting_link: string;
  minutes_used: number;
  recorded_at: string;
  started_at?: string | null;
  ended_at?: string | null;
}

export interface BackendUsageRecordListResponse {
  records: BackendUsageRecordResponse[];
  total: number;
  page: number;
  per_page: number;
}

export interface BackendCreditTransactionListResponse {
  transactions: Array<{
    id: string;
    meeting_id?: string | null;
    amount: number;
    balance_after: number;
    transaction_type: string;
    description: string;
    stripe_session_id?: string | null;
    created_at: string;
  }>;
  total: number;
  page: number;
  per_page: number;
}

export function transformStats(
  usage: BackendUsageSummaryResponse | null | undefined,
  credits: BackendCreditBalanceResponse | null | undefined
): DashboardStatsDTO {
  return {
    minutesUsedThisMonth: Math.round(usage?.total_minutes ?? 0),
    minutesRemaining: credits?.credits ?? 0,
    meetingsJoinedThisMonth: usage?.meeting_count ?? 0
  };
}

export function transformUsageRecord(backend: BackendUsageRecordResponse): UsageRecordDTO {
  return {
    id: String(backend.id),
    meetingId: String(backend.meeting_id),
    meetingTitle: `${mapPlatformDisplay(backend.platform)} Meeting`,
    minutesUsed: Math.round(backend.minutes_used ?? 0),
    usedAt: backend.recorded_at
  };
}
