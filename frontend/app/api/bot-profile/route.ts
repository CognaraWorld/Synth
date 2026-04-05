import { NextRequest } from "next/server";
import { getBotProfile, upsertBotProfile } from "@/lib/data/bot-profile";
import { successResponse, errorResponse } from "@/lib/api-response";

export async function GET() {
  const bot = await getBotProfile();
  return successResponse(bot);
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const bot = await upsertBotProfile(body);
    return successResponse(bot);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";
    return errorResponse(message);
  }
}
