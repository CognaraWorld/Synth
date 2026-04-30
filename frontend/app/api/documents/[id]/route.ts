import { NextRequest } from "next/server";
import { successResponse } from "@/lib/api-response";
import { backendDelete } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: { id: string } }
) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    await backendDelete<void>(`/api/documents/${params.id}`, token);
    return successResponse({ id: params.id });
  } catch (error) {
    return backendErrorResponse(error, "Delete failed");
  }
}
