import { getBackendToken } from "@/lib/auth/session";
import { backendGet, backendPost, backendPut } from "@/lib/backend-client";
import {
  type BackendMeetingOverrideResponse,
  type BackendMeetingResponse,
  transformMeeting,
  transformMeetingForCreate,
  transformMeetingOverride,
  transformMeetingOverrideForUpsert
} from "@/lib/transformers/meetings";
import { createMeetingSchema, meetingOverrideSchema } from "@/lib/validators/meeting";

export async function getMeetings() {
  const token = await getBackendToken();
  if (!token) {
    throw new Error("Not authenticated");
  }
  const meetings = await backendGet<BackendMeetingResponse[]>("/api/meetings/", token);
  return meetings.map(transformMeeting);
}

export async function createMeeting(input: unknown) {
  const payload = createMeetingSchema.parse(input);
  const token = await getBackendToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const meeting = await backendPost<BackendMeetingResponse>(
    "/api/meetings/",
    transformMeetingForCreate(payload),
    token
  );

  return transformMeeting(meeting);
}

export async function updateMeetingOverride(meetingId: string, input: unknown) {
  const payload = meetingOverrideSchema.parse(input);
  const token = await getBackendToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const override = await backendPut<BackendMeetingOverrideResponse>(
    `/api/meetings/${meetingId}/override`,
    transformMeetingOverrideForUpsert(payload),
    token
  );

  return transformMeetingOverride(override);
}
