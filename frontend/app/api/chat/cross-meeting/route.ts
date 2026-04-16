import { NextRequest } from "next/server";
import { z } from "zod";
import { successResponse, errorResponse } from "@/lib/api-response";
import { backendPost } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";
import type { BackendChatResponse } from "@/lib/transformers/chat";

const crossMeetingSchema = z.object({
  message: z.string().min(1).max(5000),
  meeting_ids: z.array(z.string().uuid()).optional(),
});

export async function POST(request: NextRequest) {
  const token = await requireBackendToken();
  if (!token) return notAuthenticatedResponse();

  try {
    const raw = await request.json();
    const parsed = crossMeetingSchema.safeParse(raw);
    if (!parsed.success) {
      return errorResponse("Invalid request.", 400);
    }

    const response = await backendPost<BackendChatResponse>("/api/chat/cross-meeting", parsed.data, token);
    return successResponse(response);
  } catch (error) {
    return backendErrorResponse(error, "Cross-meeting chat failed");
  }
}
