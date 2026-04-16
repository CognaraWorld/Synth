import { NextRequest } from "next/server";
import { getBotProfile, upsertBotProfile } from "@/lib/data/bot-profile";
import { successResponse, errorResponse } from "@/lib/api-response";
import { notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET() {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }
  const bot = await getBotProfile();
  return successResponse(bot);
}

export async function PUT(request: NextRequest) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }
  try {
    const body = await request.json();
    const bot = await upsertBotProfile(body);
    return successResponse(bot);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";
    return errorResponse(message);
  }
}
