import { getBackendToken } from "@/lib/auth/session";
import { backendGet } from "@/lib/backend-client";
import {
  sampleBotProfile,
  sampleCalendarConnections,
  sampleCalendarMeetings,
  sampleHomeData,
  sampleMeetings,
  sampleReports,
  sampleUsageRecords
} from "@/lib/sample-data";
import {
  type BackendCreditBalanceResponse,
  type BackendUsageRecordListResponse,
  type BackendUsageSummaryResponse,
  transformStats,
  transformUsageRecord
} from "@/lib/transformers/billing";
import {
  type BackendBotProfileResponse,
  type BackendDocumentResponse,
  transformBotProfile,
  transformDocument
} from "@/lib/transformers/bot-profile";
import { type BackendMeetingResponse, transformMeeting } from "@/lib/transformers/meetings";
import { type BackendReportListResponse, transformReport } from "@/lib/transformers/reports";

function sortByScheduledTime(meetings: ReturnType<typeof transformMeeting>[]) {
  return [...meetings].sort(
    (left, right) => new Date(left.scheduledTime).getTime() - new Date(right.scheduledTime).getTime()
  );
}

async function loadBotProfileWithDocuments(token: string) {
  const bot = await backendGet<BackendBotProfileResponse>("/api/bot/profile", token);
  const documents = await backendGet<BackendDocumentResponse[]>(`/api/documents/${bot.id}`, token).catch(
    () => []
  );

  return {
    ...transformBotProfile(bot),
    documents: documents.map(transformDocument)
  };
}

export async function getDashboardHomeData() {
  const token = await getBackendToken();
  if (!token) return sampleHomeData;

  try {
    const [meetings, reports, usage, credits] = await Promise.all([
      backendGet<BackendMeetingResponse[]>("/api/meetings/", token),
      backendGet<BackendReportListResponse>("/api/reports/?per_page=3", token),
      backendGet<BackendUsageSummaryResponse>("/api/usage/summary", token),
      backendGet<BackendCreditBalanceResponse>("/api/credits/balance", token)
    ]);

    return {
      stats: transformStats(usage, credits),
      upcomingMeetings: sortByScheduledTime(
        meetings.map(transformMeeting).filter((meeting) => meeting.status === "SCHEDULED")
      ).slice(0, 3),
      recentReports: reports.reports.map(transformReport).slice(0, 3)
    };
  } catch (err) {
    console.error("[dashboard] getDashboardHomeData failed:", err);
    return sampleHomeData;
  }
}

export async function getDashboardBillingData() {
  const token = await getBackendToken();
  if (!token) return { usageRecords: sampleUsageRecords, stats: sampleHomeData.stats };

  try {
    const [usage, credits, records] = await Promise.all([
      backendGet<BackendUsageSummaryResponse>("/api/usage/summary", token),
      backendGet<BackendCreditBalanceResponse>("/api/credits/balance", token),
      backendGet<BackendUsageRecordListResponse>("/api/usage/records?per_page=100", token),
    ]);

    return {
      usageRecords: records.records.map(transformUsageRecord),
      stats: transformStats(usage, credits)
    };
  } catch (err) {
    console.error("[dashboard] getDashboardBillingData failed:", err);
    return { usageRecords: sampleUsageRecords, stats: sampleHomeData.stats };
  }
}

export async function getCalendarData() {
  // Backend has no calendar endpoints yet — always return sample data.
  return { connections: sampleCalendarConnections, meetings: sampleCalendarMeetings };
}

export async function getBotOverviewData() {
  const token = await getBackendToken();
  if (!token) return { bot: sampleBotProfile, meetings: sampleMeetings, reports: sampleReports };

  try {
    const [bot, meetings, reports] = await Promise.all([
      loadBotProfileWithDocuments(token),
      backendGet<BackendMeetingResponse[]>("/api/meetings/", token),
      backendGet<BackendReportListResponse>("/api/reports/?per_page=100", token)
    ]);

    return {
      bot,
      meetings: meetings.map(transformMeeting),
      reports: reports.reports.map(transformReport)
    };
  } catch (err) {
    console.error("[dashboard] getBotOverviewData failed:", err);
    return { bot: sampleBotProfile, meetings: sampleMeetings, reports: sampleReports };
  }
}
