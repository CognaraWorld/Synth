export type ResponseMode = "WAKE_WORD_ONLY" | "PROACTIVE";
export type MeetingStatus = "SCHEDULED" | "LIVE" | "COMPLETED" | "CANCELLED";
export type VoiceOption = "MALE" | "FEMALE";

export interface ActionItem {
  id: string;
  label: string;
  done: boolean;
  owner?: string;
}

export interface GlobalDocumentDTO {
  id: string;
  name: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  fileUrl: string;
  createdAt: string;
}

export interface BotProfileDTO {
  id: string;
  name: string;
  persona: string;
  voice: VoiceOption;
  responseMode: ResponseMode;
  createdAt: string;
  updatedAt: string;
  documents: GlobalDocumentDTO[];
}

export interface MeetingOverrideDTO {
  id: string;
  meetingId: string;
  personaOverride?: string | null;
  voiceOverride?: VoiceOption | null;
  responseModeOverride?: ResponseMode | null;
  documents: GlobalDocumentDTO[];
}

export interface MeetingDTO {
  id: string;
  title: string;
  joinUrl: string;
  platform: "Zoom" | "Google Meet" | "Microsoft Teams" | "Manual";
  scheduledTime: string;
  endTime?: string | null;
  status: MeetingStatus;
  durationMinutes?: number | null;
  botJoined: boolean;
  notes?: string | null;
  override?: MeetingOverrideDTO | null;
}

export interface LiveSessionDTO {
  id: string;
  meetingId: string;
  status: "LISTENING" | "THINKING" | "SPEAKING" | "MUTED";
  startedAt: string;
}

export interface ReportDTO {
  id: string;
  meetingId: string;
  meetingTitle: string;
  scheduledTime: string;
  durationMinutes: number;
  summary: string;
  actionItems: ActionItem[];
  pdfUrl: string;
  wordUrl: string;
}

export interface CalendarMeetingIndicator {
  id: string;
  title: string;
  start: string;
  end: string;
  botJoined: boolean;
}

export interface CalendarConnectionDTO {
  id: string;
  provider: "GOOGLE" | "OUTLOOK";
  connectedAt: string;
  autoJoinAll: boolean;
}

export interface DashboardStatsDTO {
  minutesUsedThisMonth: number;
  minutesRemaining: number;
  meetingsJoinedThisMonth: number;
}

export interface UsageRecordDTO {
  id: string;
  meetingId: string;
  meetingTitle: string;
  minutesUsed: number;
  usedAt: string;
}

export interface DashboardHomeDTO {
  stats: DashboardStatsDTO;
  upcomingMeetings: MeetingDTO[];
  recentReports: ReportDTO[];
}

export interface TranscriptChunkDTO {
  id: string;
  speaker: string;
  text: string;
  timestamp: string;
  isBot?: boolean;
}

export interface TranscriptSocketEvent {
  type: "chunk" | "status" | "reset";
  payload: TranscriptChunkDTO | { status: LiveSessionDTO["status"] } | null;
}
