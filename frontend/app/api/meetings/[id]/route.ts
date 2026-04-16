import { NextRequest } from "next/server";
import { updateMeetingOverride } from "@/lib/data/meetings";
import { successResponse, errorResponse } from "@/lib/api-response";
import { notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function PATCH(request: NextRequest, { params }: { params: { id: string } }) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }
  try {
    const body = await request.json();
    const override = await updateMeetingOverride(params.id, body);
    return successResponse(override);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";
    return errorResponse(message);
  }
}
