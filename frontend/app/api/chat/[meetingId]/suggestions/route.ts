import { NextRequest } from "next/server";
import { successResponse } from "@/lib/api-response";
import { backendGet } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET(_: NextRequest, { params }: { params: { meetingId: string } }) {
  const token = await requireBackendToken();
  if (!token) return notAuthenticatedResponse();

  try {
    const data = await backendGet<{ suggestions: string[] }>(
      `/api/meetings/${params.meetingId}/chat/suggestions`,
      token
    );
    return successResponse(data);
  } catch (error) {
    return backendErrorResponse(error, "Failed to load suggestions");
  }
}
