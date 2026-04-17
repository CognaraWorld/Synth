import { NextRequest } from "next/server";
import { getMeetings, createMeeting } from "@/lib/data/meetings";
import { successResponse } from "@/lib/api-response";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET() {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }
  try {
    const meetings = await getMeetings();
    return successResponse(meetings);
  } catch (error) {
    return backendErrorResponse(error, "Failed to load meetings");
  }
}

export async function POST(request: NextRequest) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }
  try {
    const body = await request.json();
    const meeting = await createMeeting(body);
    return successResponse(meeting, { status: 201 });
  } catch (error) {
    return backendErrorResponse(error, "Failed to create meeting");
  }
}
