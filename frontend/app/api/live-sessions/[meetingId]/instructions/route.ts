import { NextRequest } from "next/server";
import { successResponse } from "@/lib/api-response";
import { backendPost } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function POST(request: NextRequest, { params }: { params: { meetingId: string } }) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const body = await request.json();
    const result = await backendPost(`/api/live-sessions/${params.meetingId}/instructions`, body, token);
    return successResponse(result);
  } catch (error) {
    return backendErrorResponse(error, "Failed to send instruction");
  }
}
