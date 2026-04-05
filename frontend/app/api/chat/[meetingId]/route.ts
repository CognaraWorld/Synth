import { NextRequest } from "next/server";
import { z } from "zod";
import { successResponse, errorResponse } from "@/lib/api-response";
import { backendGet, backendPost } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";
import type { BackendChatHistoryResponse, BackendChatResponse } from "@/lib/transformers/chat";

const chatMessageSchema = z.object({
  message: z.string().min(1).max(5000),
});

export async function GET(request: NextRequest, { params }: { params: { meetingId: string } }) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    // Forward query params (per_page, before) to backend
    const { searchParams } = new URL(request.url);
    const qs = searchParams.toString();
    const path = `/api/meetings/${params.meetingId}/chat/history${qs ? `?${qs}` : ""}`;
    const history = await backendGet<BackendChatHistoryResponse>(path, token);
    return successResponse(history);
  } catch (error) {
    return backendErrorResponse(error, "Failed to load chat history");
  }
}

export async function POST(request: NextRequest, { params }: { params: { meetingId: string } }) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const raw = await request.json();
    const parsed = chatMessageSchema.safeParse(raw);
    if (!parsed.success) {
      return errorResponse("Message is required (1-5000 characters).", 400);
    }

    const response = await backendPost<BackendChatResponse>(
      `/api/meetings/${params.meetingId}/chat`,
      parsed.data,
      token
    );
    return successResponse(response);
  } catch (error) {
    return backendErrorResponse(error, "Failed to send chat message");
  }
}
