import { successResponse } from "@/lib/api-response";
import { backendPostEmpty } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function POST(_: Request, { params }: { params: { meetingId: string } }) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const result = await backendPostEmpty(`/api/reports/meetings/${params.meetingId}/generate`, token);
    return successResponse(result);
  } catch (error) {
    return backendErrorResponse(error, "Failed to generate report");
  }
}
