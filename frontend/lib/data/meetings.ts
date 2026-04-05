import { getBackendToken } from "@/lib/auth/session";
import { backendGet, backendPost, backendPut } from "@/lib/backend-client";
import { sampleMeetings } from "@/lib/sample-data";
import {
  type BackendMeetingOverrideResponse,
  type BackendMeetingResponse,
  transformMeeting,
  transformMeetingForCreate,
  transformMeetingOverride,
  transformMeetingOverrideForUpsert
} from "@/lib/transformers/meetings";
import { createMeetingSchema, meetingOverrideSchema } from "@/lib/validators/meeting";

function buildFallbackMeeting(input: ReturnType<typeof createMeetingSchema.parse>) {
  return {
    id: `meeting_${Date.now()}`,
    title: input.title ?? "Instant Meeting",
    joinUrl: input.joinUrl,
    scheduledTime: input.scheduledTime ?? new Date().toISOString(),
    endTime: null,
    platform: input.platform,
    status: "SCHEDULED" as const,
    durationMinutes: 30,
    botJoined: false,
    notes: null
  };
}

function buildFallbackOverride(meetingId: string, input: ReturnType<typeof meetingOverrideSchema.parse>) {
  return {
    id: `override_${meetingId}`,
    meetingId,
    ...input,
    documents: []
  };
}

export async function getMeetings() {
  const token = await getBackendToken();
  if (!token) return sampleMeetings;

  try {
    const meetings = await backendGet<BackendMeetingResponse[]>("/api/meetings/", token);
    return meetings.map(transformMeeting);
  } catch (err) {
    console.error("[meetings] getMeetings failed:", err);
    return sampleMeetings;
  }
}

export async function createMeeting(input: unknown) {
  const payload = createMeetingSchema.parse(input);
  const fallback = buildFallbackMeeting(payload);
  const token = await getBackendToken();

  if (!token) {
    return fallback;
  }

  try {
    const meeting = await backendPost<BackendMeetingResponse>(
      "/api/meetings/",
      transformMeetingForCreate(payload),
      token
    );

    return transformMeeting(meeting);
  } catch (err) {
    console.error("[meetings] createMeeting failed:", err);
    return fallback;
  }
}

export async function updateMeetingOverride(meetingId: string, input: unknown) {
  const payload = meetingOverrideSchema.parse(input);
  const fallback = buildFallbackOverride(meetingId, payload);
  const token = await getBackendToken();

  if (!token) {
    return fallback;
  }

  const body = transformMeetingOverrideForUpsert(payload);
  if (Object.keys(body).length === 0) {
    return fallback;
  }

  try {
    const override = await backendPut<BackendMeetingOverrideResponse>(
      `/api/meetings/${meetingId}/override`,
      body,
      token
    );

    return transformMeetingOverride(override);
  } catch (err) {
    console.error("[meetings] updateMeetingOverride failed:", err);
    return fallback;
  }
}
