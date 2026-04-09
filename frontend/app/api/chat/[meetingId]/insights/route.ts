import { NextRequest } from "next/server";
import { backendFetch } from "@/lib/backend-client";
import { notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET(_: NextRequest, { params }: { params: { meetingId: string } }) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const response = await backendFetch(`/api/meetings/${params.meetingId}/chat/insights/stream`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    return new Response(response.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch {
    return new Response("Insights stream unavailable", { status: 502 });
  }
}
