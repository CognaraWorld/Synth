import type { MeetingDTO, MeetingOverrideDTO, ResponseMode, VoiceOption } from "@/types";

export interface BackendMeetingResponse {
  id: string;
  agent_id: string;
  platform: string;
  meeting_link: string;
  status: string;
  started_at?: string | null;
  ended_at?: string | null;
  duration_minutes?: number | null;
  created_at: string;
  override?: BackendMeetingOverrideResponse | null;
}

export interface BackendMeetingOverrideResponse {
  id: string;
  meeting_id: string;
  description?: string | null;
  mode?: string | null;
  persona_id?: string | null;
  system_prompt?: string | null;
  voice?: string | null;
  response_mode?: string | null;
  created_at?: string;
  updated_at?: string;
}

type DashboardMeetingCreateInput = {
  joinUrl: string;
};

type DashboardMeetingOverrideInput = {
  personaOverride?: string | null;
  voiceOverride?: VoiceOption | null;
  responseModeOverride?: ResponseMode | null;
};

type BackendMeetingCreatePayload = {
  meeting_link: string;
};

type BackendMeetingOverridePayload = {
  description?: string | null;
  voice?: "male" | "female" | null;
  response_mode?: "name_only" | "proactive" | null;
};

function mapResponseMode(mode: string | null | undefined): ResponseMode | null {
  if (!mode) return null;
  return mode === "proactive" ? "PROACTIVE" : "WAKE_WORD_ONLY";
}

export function mapPlatformDisplay(platform: string | null | undefined): MeetingDTO["platform"] {
  switch ((platform ?? "").toLowerCase()) {
    case "zoom":
      return "Zoom";
    case "teams":
      return "Microsoft Teams";
    case "google_meet":
    case "meet":
      return "Google Meet";
    default:
      return "Manual";
  }
}

export function mapStatus(status: string | null | undefined): MeetingDTO["status"] {
  switch ((status ?? "").toLowerCase()) {
    case "active":
      return "LIVE";
    case "ended":
      return "COMPLETED";
    case "failed":
      return "CANCELLED";
    case "joining":
    case "pending":
    default:
      return "SCHEDULED";
  }
}

export function transformMeetingOverride(backend: BackendMeetingOverrideResponse): MeetingOverrideDTO {
  return {
    id: String(backend.id),
    meetingId: String(backend.meeting_id),
    personaOverride: backend.description ?? null,
    voiceOverride: backend.voice ? (backend.voice.toUpperCase() as VoiceOption) : null,
    responseModeOverride: mapResponseMode(backend.response_mode),
    documents: []
  };
}

export function transformMeeting(backend: BackendMeetingResponse): MeetingDTO {
  const platform = mapPlatformDisplay(backend.platform);

  return {
    id: String(backend.id),
    title: `${platform} Meeting`,
    joinUrl: backend.meeting_link,
    platform,
    scheduledTime: backend.created_at,
    endTime: backend.ended_at ?? null,
    status: mapStatus(backend.status),
    durationMinutes: Math.round(backend.duration_minutes ?? 0),
    botJoined: backend.status !== "pending",
    notes: null,
    override: backend.override ? transformMeetingOverride(backend.override) : null
  };
}

export function transformMeetingForCreate(input: DashboardMeetingCreateInput): BackendMeetingCreatePayload {
  return {
    meeting_link: input.joinUrl
  };
}

export function transformMeetingOverrideForUpsert(
  input: DashboardMeetingOverrideInput
): BackendMeetingOverridePayload {
  const payload: BackendMeetingOverridePayload = {};

  if (input.personaOverride !== undefined) {
    payload.description = input.personaOverride ?? null;
  }

  if (input.voiceOverride !== undefined) {
    payload.voice = (input.voiceOverride?.toLowerCase() as "male" | "female" | undefined) ?? null;
  }

  if (input.responseModeOverride !== undefined) {
    payload.response_mode = input.responseModeOverride === null
      ? null
      : input.responseModeOverride === "PROACTIVE" ? "proactive" : "name_only";
  }

  return payload;
}
