import { NextRequest } from "next/server";
import { getBotProfile, upsertBotProfile } from "@/lib/data/bot-profile";
import { successResponse } from "@/lib/api-response";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

export async function GET() {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }
  try {
    const bot = await getBotProfile();
    return successResponse(bot);
  } catch (error) {
    return backendErrorResponse(error, "Failed to load bot profile");
  }
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
    return backendErrorResponse(error, "Failed to update bot profile");
  }
}
