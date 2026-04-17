import { NextRequest } from "next/server";
import { z } from "zod";
import { successResponse, errorResponse } from "@/lib/api-response";
import { backendPost } from "@/lib/backend-client";
import {
  backendErrorResponse,
  notAuthenticatedResponse,
  requireBackendToken,
} from "@/lib/backend-proxy";

const instructionSchema = z.object({
  instruction: z.string().trim().min(1).max(2000),
});

export async function POST(
  request: NextRequest,
  { params }: { params: { meetingId: string } },
) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const raw = await request.json();
    const parsed = instructionSchema.safeParse(raw);
    if (!parsed.success) {
      return errorResponse(
        "instruction must be a non-empty string under 2000 characters",
        400,
      );
    }
    const result = await backendPost(
      `/api/live-sessions/${params.meetingId}/instructions`,
      parsed.data,
      token,
    );
    return successResponse(result);
  } catch (error) {
    return backendErrorResponse(error, "Failed to send instruction");
  }
}
