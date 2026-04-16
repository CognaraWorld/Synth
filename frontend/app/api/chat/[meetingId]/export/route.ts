import { NextRequest } from "next/server";
import { backendFetch } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET(_: NextRequest, { params }: { params: { meetingId: string } }) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const response = await backendFetch(`/api/meetings/${params.meetingId}/chat/export`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    return new Response(response.body, {
      headers: {
        "Content-Type": response.headers.get("Content-Type") || "text/markdown",
        "Content-Disposition": response.headers.get("Content-Disposition") || 'attachment; filename="chat-notes.md"',
      },
    });
  } catch (error) {
    return backendErrorResponse(error, "Export failed");
  }
}
