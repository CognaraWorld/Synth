import { successResponse } from "@/lib/api-response";
import { backendGet } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET(_: Request, { params }: { params: { meetingId: string } }) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const liveSession = await backendGet(`/api/live-sessions/${params.meetingId}`, token);
    return successResponse(liveSession);
  } catch (error) {
    return backendErrorResponse(error, "Failed to load live session");
  }
}
